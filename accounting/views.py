from django.shortcuts import render
from django.views.generic import ListView
from django.db.models import Sum, Q
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import JournalEntry, Account

class JournalEntryListView(LoginRequiredMixin, ListView):
    model = JournalEntry
    template_name = 'accounting/journal_entry_list.html'
    context_object_name = 'entries'
    paginate_by = 50

    def get_queryset(self):
        return JournalEntry.objects.filter(created_by=self.request.user).prefetch_related('items__account').order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add summary stats if needed
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
