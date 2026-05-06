import csv
from datetime import date
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.db.models import Sum, Q, Count, F, Case, When, Value, BooleanField, DecimalField
from django.db.models.functions import Coalesce
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db import transaction

from .models import JournalEntry, JournalItem, Account
from .forms import JournalEntryForm, JournalItemFormSet


class JournalEntryListView(LoginRequiredMixin, ListView):
    """Libro Diario — filterable, KPI-driven view of every Journal Entry.

    Annotates each row with totals so balance/posting state can be rendered
    without forcing a per-entry query, and exposes filters for date range,
    account, status and free-text search.
    """
    model = JournalEntry
    template_name = 'accounting/journal_entry_list.html'
    context_object_name = 'entries'
    paginate_by = 50

    def _base_qs(self):
        return JournalEntry.objects.filter(created_by=self.request.user)

    def get_queryset(self):
        qs = self._base_qs().prefetch_related('items__account', 'items__partner').annotate(
            total_debit=Coalesce(Sum('items__debit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
            total_credit=Coalesce(Sum('items__credit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
            line_count=Count('items'),
        ).annotate(
            balanced=Case(
                When(total_debit=F('total_credit'), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

        search = (self.request.GET.get('q') or '').strip()
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(reference__icontains=search)
                | Q(items__account__name__icontains=search)
                | Q(items__account__code__icontains=search)
            ).distinct()

        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        account_id = self.request.GET.get('account')
        if account_id and account_id.isdigit():
            qs = qs.filter(items__account_id=int(account_id)).distinct()

        status = self.request.GET.get('status')
        if status == 'POSTED':
            qs = qs.filter(posted=True)
        elif status == 'DRAFT':
            qs = qs.filter(posted=False)
        elif status == 'UNBALANCED':
            qs = qs.exclude(total_debit=F('total_credit'))

        return qs.order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = self._base_qs()
        today = date.today()
        month_start = today.replace(day=1)

        agg = base.annotate(
            ent_debit=Coalesce(Sum('items__debit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
            ent_credit=Coalesce(Sum('items__credit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
        ).aggregate(
            total_count=Count('id'),
            total_debit=Sum('ent_debit'),
            total_credit=Sum('ent_credit'),
            posted_count=Count('id', filter=Q(posted=True)),
            month_count=Count('id', filter=Q(date__gte=month_start)),
        )

        # Unbalanced detection: per-entry comparison; can't aggregate via simple
        # filter, so list the offending IDs and count them.
        unbalanced_ids = list(
            base.annotate(
                td=Coalesce(Sum('items__debit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
                tc=Coalesce(Sum('items__credit'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
            ).exclude(td=F('tc')).values_list('id', flat=True)
        )

        context.update({
            'accounts': Account.objects.filter(is_active=True).order_by('code'),
            'kpi_total_count': agg['total_count'] or 0,
            'kpi_total_debit': agg['total_debit'] or 0,
            'kpi_total_credit': agg['total_credit'] or 0,
            'kpi_posted_count': agg['posted_count'] or 0,
            'kpi_draft_count': (agg['total_count'] or 0) - (agg['posted_count'] or 0),
            'kpi_unbalanced_count': len(unbalanced_ids),
            'kpi_month_count': agg['month_count'] or 0,
            'filter_status': self.request.GET.get('status', ''),
            'filter_account': self.request.GET.get('account', ''),
            'filter_date_from': self.request.GET.get('date_from', ''),
            'filter_date_to': self.request.GET.get('date_to', ''),
            'search_query': self.request.GET.get('q', ''),
        })
        return context


class TrialBalanceView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'accounting/trial_balance.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        user = self.request.user
        return Account.objects.annotate(
            total_debit=Sum('journal_items__debit', filter=Q(journal_items__journal_entry__created_by=user), default=0),
            total_credit=Sum('journal_items__credit', filter=Q(journal_items__journal_entry__created_by=user), default=0)
        ).order_by('code')


# ---------------------------------------------------------------------------
# Manual journal entry CRUD
# ---------------------------------------------------------------------------

@login_required
def ledger_detail(request, pk):
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('items__account', 'items__partner'),
        pk=pk,
        created_by=request.user,
    )
    total_debit = sum((i.debit for i in entry.items.all()), Decimal('0'))
    total_credit = sum((i.credit for i in entry.items.all()), Decimal('0'))
    return render(request, 'accounting/journal_entry_detail.html', {
        'entry': entry,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'is_balanced': total_debit == total_credit,
    })


@login_required
def ledger_create(request):
    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        formset = JournalItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                entry = form.save(commit=False)
                entry.created_by = request.user
                entry.save()
                formset.instance = entry
                formset.save()
            messages.success(request, f'Asiento #{entry.id} creado.')
            return redirect('accounting_ledger')
        messages.error(request, 'Revisa los errores en el formulario.')
    else:
        form = JournalEntryForm(initial={'date': date.today()})
        formset = JournalItemFormSet(prefix='items')
    return render(request, 'accounting/journal_entry_form.html', {
        'form': form,
        'formset': formset,
        'mode': 'create',
    })


@login_required
def ledger_edit(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, created_by=request.user)
    if entry.posted:
        messages.warning(request, 'Asiento contabilizado: desmarcá "posted" para editarlo.')
        return redirect('accounting_ledger_detail', pk=entry.pk)
    if request.method == 'POST':
        form = JournalEntryForm(request.POST, instance=entry)
        formset = JournalItemFormSet(request.POST, instance=entry, prefix='items')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, f'Asiento #{entry.id} actualizado.')
            return redirect('accounting_ledger')
        messages.error(request, 'Revisa los errores en el formulario.')
    else:
        form = JournalEntryForm(instance=entry)
        formset = JournalItemFormSet(instance=entry, prefix='items')
    return render(request, 'accounting/journal_entry_form.html', {
        'form': form,
        'formset': formset,
        'entry': entry,
        'mode': 'edit',
    })


@login_required
def ledger_delete(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, created_by=request.user)
    if request.method == 'POST':
        if entry.posted:
            messages.error(request, 'No se puede eliminar un asiento contabilizado.')
            return redirect('accounting_ledger_detail', pk=entry.pk)
        entry.delete()
        messages.success(request, 'Asiento eliminado.')
        return redirect('accounting_ledger')
    return render(request, 'accounting/journal_entry_confirm_delete.html', {'entry': entry})


@login_required
def ledger_toggle_post(request, pk):
    """Flip the posted flag. Refuses to post unbalanced entries."""
    entry = get_object_or_404(JournalEntry, pk=pk, created_by=request.user)
    if request.method != 'POST':
        return redirect('accounting_ledger')
    if not entry.posted and not entry.is_balanced:
        messages.error(request, 'No se puede contabilizar: el asiento está desbalanceado.')
        return redirect('accounting_ledger_detail', pk=entry.pk)
    entry.posted = not entry.posted
    entry.save(update_fields=['posted', 'updated_at'])
    messages.success(request, f"Asiento {'contabilizado' if entry.posted else 'reabierto a borrador'}.")
    return redirect('accounting_ledger')


@login_required
def ledger_export_csv(request):
    """Download every (filter-respecting) line of the ledger as CSV."""
    qs = JournalItem.objects.filter(
        journal_entry__created_by=request.user,
    ).select_related('journal_entry', 'account', 'partner').order_by(
        '-journal_entry__date', 'journal_entry__id'
    )

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        qs = qs.filter(journal_entry__date__gte=date_from)
    if date_to:
        qs = qs.filter(journal_entry__date__lte=date_to)
    account_id = request.GET.get('account')
    if account_id and account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="libro_diario.csv"'
    response.write('﻿')  # BOM so Excel detects UTF-8

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Fecha', 'Asiento', 'Descripción', 'Referencia',
                     'Cuenta Código', 'Cuenta Nombre', 'Debe', 'Haber',
                     'Detalle Línea', 'Estado'])
    for it in qs:
        je = it.journal_entry
        writer.writerow([
            je.date.strftime('%Y-%m-%d'),
            je.id,
            je.description,
            je.reference or '',
            it.account.code,
            it.account.name,
            f'{it.debit:.2f}',
            f'{it.credit:.2f}',
            it.description or '',
            'Contabilizado' if je.posted else 'Borrador',
        ])
    return response
