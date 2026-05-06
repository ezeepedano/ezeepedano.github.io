
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView, CreateView
from django.urls import reverse_lazy
from decimal import Decimal
from datetime import date, timedelta
from django.contrib import messages
import logging
from django.db import models, transaction
from django.db.models import Sum, Avg, Count, F

_payment_logger = logging.getLogger('finance.payments')
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import FixedCost, MonthlyExpense, Purchase, Provider, PurchaseCategory, Asset, AssetCategory, Account, CashMovement
from .forms import FixedCostForm, PurchaseForm, VariableExpenseForm, AssetForm, ProviderForm, TransactionImportForm, AccountForm
from .services import FinanceReportService, ExpenseService, FinanceService
from .importers.mercadopago_cash import MercadoPagoCashImporter
from sales.models import Sale

@login_required
def fixed_cost_list(request):
    """Monthly expenses dashboard.

    Builds the full month/year navigator + KPIs + history summary that the
    template needs, in addition to the basic figures provided by
    FinanceReportService. Fixed and variable expenses are split based on
    whether they're tied to a recurring template (FixedCost) or stand
    alone (caja chica).
    """
    from datetime import date as _date
    today = timezone.now().date()
    try:
        view_year = int(request.GET.get('year') or today.year)
        view_month = int(request.GET.get('month') or today.month)
        if not (1 <= view_month <= 12):
            view_month = today.month
    except (TypeError, ValueError):
        view_year, view_month = today.year, today.month

    current_month = _date(view_year, view_month, 1)
    # Prev/next month
    if view_month == 1:
        prev_month = _date(view_year - 1, 12, 1)
    else:
        prev_month = _date(view_year, view_month - 1, 1)
    if view_month == 12:
        next_month = _date(view_year + 1, 1, 1)
    else:
        next_month = _date(view_year, view_month + 1, 1)

    base_ctx = FinanceReportService.get_dashboard_context(view_year, view_month, request.user)
    expenses = base_ctx['monthly_expenses']

    # Split fixed vs variable: fixed = tied to a recurring FixedCost template.
    fixed_expenses = expenses.filter(cost_definition__isnull=False).select_related('cost_definition')
    variable_expenses = expenses.filter(cost_definition__isnull=True)

    # Month-of-year navigator with status pills (Pagado / Pendiente / Sin datos).
    months_nav = []
    for m in range(1, 13):
        m_date = _date(view_year, m, 1)
        m_qs = MonthlyExpense.objects.filter(user=request.user, month=m_date)
        total = m_qs.aggregate(t=Sum('amount'))['t'] or 0
        paid = m_qs.filter(is_paid=True).aggregate(t=Sum('amount'))['t'] or 0
        months_nav.append({
            'num': m,
            'date': m_date,
            'has_data': bool(total),
            'is_paid': total > 0 and paid >= total,
        })

    # Year list = years with at least one MonthlyExpense, plus current year.
    years_with_data = MonthlyExpense.objects.filter(user=request.user).dates('month', 'year', order='DESC')
    available_years = sorted({y.year for y in years_with_data} | {today.year, view_year}, reverse=True)

    # History summary: per-month totals for prior 6 months.
    history_summary = []
    for back in range(1, 7):
        m_year = view_year
        m_month = view_month - back
        while m_month <= 0:
            m_month += 12
            m_year -= 1
        m_date = _date(m_year, m_month, 1)
        m_qs = MonthlyExpense.objects.filter(user=request.user, month=m_date)
        total = m_qs.aggregate(t=Sum('amount'))['t'] or 0
        paid = m_qs.filter(is_paid=True).aggregate(t=Sum('amount'))['t'] or 0
        if total or paid:
            history_summary.append({
                'month': m_date,
                'total': total,
                'paid': paid,
                'count': m_qs.count(),
            })

    # Year stats.
    year_qs = MonthlyExpense.objects.filter(user=request.user, month__year=view_year)
    total_year_spent = year_qs.filter(is_paid=True).aggregate(t=Sum('amount'))['t'] or 0
    months_with_data = year_qs.filter(is_paid=True).dates('month', 'month').count() or 1
    average_monthly = total_year_spent / months_with_data if months_with_data else 0

    # KPIs for the *current* selected month (so users see what changed when
    # they navigate). Counts use MonthlyExpense, not Purchase.
    total_amount = base_ctx['total_expenses']
    total_paid = base_ctx['total_paid']
    total_pending = base_ctx['total_pending']
    overdue_count = expenses.filter(is_paid=False, due_date__lt=today).count()

    # Filter purchases for the month (legacy contract).
    purchase_category_id = request.GET.get('purchase_category')
    selected_category_id = None
    purchases = base_ctx['purchases']
    if purchase_category_id:
        try:
            selected_category_id = int(purchase_category_id)
            purchases = purchases.filter(category_id=selected_category_id)
        except (TypeError, ValueError):
            selected_category_id = None
    total_purchase_amount = purchases.aggregate(Sum('amount'))['amount__sum'] or 0

    context = {
        **base_ctx,
        'today': today,
        'current_month': current_month,
        'prev_month': prev_month,
        'next_month': next_month,
        'view_year': view_year,
        'view_month': view_month,
        'months_navigation': months_nav,
        'available_years': available_years,
        'history_summary': history_summary,

        'expenses': expenses,
        'fixed_expenses': fixed_expenses,
        'variable_expenses': variable_expenses,

        'total_amount': total_amount,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'overdue_count': overdue_count,
        'total_year_spent': total_year_spent,
        'average_monthly': average_monthly,

        'purchases': purchases,
        'total_purchase_amount': total_purchase_amount,
        'purchase_categories': PurchaseCategory.objects.filter(user=request.user),
        'providers': Provider.objects.filter(user=request.user),
        'selected_category_id': selected_category_id,
    }
    return render(request, 'finance/fixed_cost_list.html', context)

@login_required
def generate_monthly_expenses(request):
    if request.method == 'POST':
        year = request.POST.get('year')
        year = int(year) if year else timezone.now().year
        month = request.POST.get('month')
        month = int(month) if month else timezone.now().month
        
        created, updated = ExpenseService.generate_monthly_expenses_from_templates(year, month, request.user)
        
        if created > 0 and updated > 0:
            msg = f'Se crearon {created} nuevos gastos y se actualizaron {updated}.'
        elif created > 0:
            msg = f'Se generaron {created} gastos exitosamente.'
        elif updated > 0:
            msg = f'Se actualizaron {updated} gastos existentes correctamente.'
        else:
            msg = 'No hay cambios para aplicar.'

        messages.success(request, msg)
        return redirect(f'/finance/costs/?year={year}&month={month}')
    return redirect('fixed_cost_list')

@login_required
def delete_monthly_expenses(request):
    if request.method == 'POST':
        year = request.POST.get('year')
        month = request.POST.get('month')
        
        if year and month:
            count = MonthlyExpense.objects.filter(
                user=request.user,
                month__year=year, 
                month__month=month
            ).delete()[0]
            
            messages.warning(request, f'Se han eliminado {count} registros del mes {month}/{year}.')
            return redirect(f'/finance/costs/?year={year}&month={month}')
            
    return redirect('fixed_cost_list')

@login_required
def toggle_payment(request, pk):
    if request.method == 'POST':
        expense = get_object_or_404(MonthlyExpense, pk=pk, user=request.user)
        status = ExpenseService.toggle_payment_status(expense)
        messages.success(request, f"{expense.name} marcado como {status}.")
        return redirect(f'/finance/costs/?year={expense.month.year}&month={expense.month.month}')
    return redirect('fixed_cost_list')

@login_required
def fixed_cost_definition_list(request):
    # This view lists the DEFINITIONS (templates)
    definitions = FixedCost.objects.filter(user=request.user).order_by('due_day')
    return render(request, 'finance/definition_list.html', {'definitions': definitions})

@login_required
def fixed_cost_create(request):
    if request.method == 'POST':
        form = FixedCostForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            messages.success(request, 'Plantilla de costo creada.')
            return redirect('fixed_cost_definition_list')
    else:
        form = FixedCostForm()
    return render(request, 'finance/fixed_cost_form.html', {'form': form, 'title': 'Nueva Plantilla de Costo'})

@login_required
def fixed_cost_edit(request, pk):
    cost = get_object_or_404(FixedCost, pk=pk, user=request.user)
    if request.method == 'POST':
        form = FixedCostForm(request.POST, instance=cost)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plantilla de costo actualizada.')
            return redirect('fixed_cost_definition_list')
    else:
        form = FixedCostForm(instance=cost)
    return render(request, 'finance/fixed_cost_form.html', {'form': form, 'title': 'Editar Plantilla de Costo'})

@login_required
def fixed_cost_delete(request, pk):
    cost = get_object_or_404(FixedCost, pk=pk, user=request.user)
    if request.method == 'POST':
        cost.delete()
        messages.success(request, 'Plantilla eliminada.')
        return redirect('fixed_cost_definition_list')
    return render(request, 'finance/fixed_cost_confirm_delete.html', {'cost': cost})

# --- Purchases Module Views ---

class PurchaseHubView(LoginRequiredMixin, TemplateView):
    """Legacy URL — kept for sidebar/back-links. The hub UI was merged
    into the unified list at /traceability/purchases/, where the
    Nueva Compra action exposes the three sub-flows in a dropdown.
    """

    def get(self, request, *args, **kwargs):
        return redirect('traceability:purchase_list')


@login_required
def purchase_edit(request, pk):
    """Edit a generic Purchase (general expense or stock-linked)."""
    purchase = get_object_or_404(Purchase, pk=pk, user=request.user)
    if request.method == 'POST':
        form = PurchaseForm(request.POST, instance=purchase)
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = PurchaseCategory.objects.filter(user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            # Keep is_paid flag in sync with payment_status so legacy code
            # that reads is_paid stays consistent.
            obj.is_paid = (obj.payment_status == 'PAID')
            if obj.payment_status == 'PAID' and obj.paid_amount < obj.amount:
                obj.paid_amount = obj.amount
            obj.save()
            messages.success(request, 'Compra actualizada.')
            return redirect('traceability:purchase_list')
        messages.error(request, f'Error de validación: {form.errors.as_text()}')
    else:
        form = PurchaseForm(instance=purchase)
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = PurchaseCategory.objects.filter(user=request.user)
    return render(request, 'finance/purchase_edit_form.html', {
        'form': form,
        'purchase': purchase,
    })


@login_required
def purchase_delete(request, pk):
    """Delete a Purchase. Confirmation required (POST only)."""
    purchase = get_object_or_404(Purchase, pk=pk, user=request.user)
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'Compra eliminada.')
        return redirect('traceability:purchase_list')
    return render(request, 'finance/purchase_confirm_delete.html', {'purchase': purchase})


@login_required
def purchase_pay(request, pk):
    """Quick-pay action: mark a purchase as paid (full or partial).

    Accepts an optional `amount` POST field for partial payments.
    Without it, marks the full balance as paid.
    """
    if request.method != 'POST':
        return redirect('traceability:purchase_list')

    raw_amount = (request.POST.get('amount') or '').strip()

    try:
        with transaction.atomic():
            # Lock the row so concurrent quick-pay clicks can't double-post
            # the same balance.
            purchase = get_object_or_404(
                Purchase.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            try:
                if raw_amount:
                    pay_amount = Decimal(raw_amount)
                else:
                    pay_amount = purchase.amount - purchase.paid_amount
            except (ValueError, TypeError):
                messages.error(request, 'Monto inválido.')
                return redirect('traceability:purchase_list')

            if pay_amount <= 0:
                messages.error(request, 'El monto a pagar debe ser mayor a cero.')
                return redirect('traceability:purchase_list')

            new_paid = purchase.paid_amount + pay_amount
            if new_paid > purchase.amount:
                new_paid = purchase.amount

            previous_status = purchase.payment_status
            purchase.paid_amount = new_paid
            if new_paid >= purchase.amount:
                purchase.payment_status = 'PAID'
                purchase.is_paid = True
            elif new_paid > 0:
                purchase.payment_status = 'PARTIAL'
                purchase.is_paid = False
            purchase.save(update_fields=['paid_amount', 'payment_status', 'is_paid', 'updated_at'])

            _payment_logger.info(
                "purchase_pay user=%s purchase=%s amount=%s status=%s->%s",
                request.user.pk, purchase.pk, pay_amount,
                previous_status, purchase.payment_status,
            )
    except Exception:
        _payment_logger.exception("purchase_pay failed user=%s pk=%s", request.user.pk, pk)
        messages.error(request, 'No se pudo registrar el pago. Intente nuevamente.')
        return redirect('traceability:purchase_list')

    messages.success(request, f'Pago registrado: ${pay_amount} en {purchase.code or purchase.description or "compra"}.')
    return redirect('traceability:purchase_list')

class GeneralPurchaseCreateView(LoginRequiredMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = 'finance/purchase_general_form.html'
    success_url = reverse_lazy('traceability:purchase_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['provider'].queryset = Provider.objects.filter(user=self.request.user)
        form.fields['category'].queryset = PurchaseCategory.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        purchase = form.save(commit=False)
        purchase.user = self.request.user
        
        # Handle inline provider creation if name passed and not selected
        provider_name = self.request.POST.get('provider_name')
        if not purchase.provider and provider_name:
            purchase.provider, _ = Provider.objects.get_or_create(
                name=provider_name.strip(),
                user=self.request.user,
                defaults={'user': self.request.user}
            )
            
        purchase.save()
        messages.success(self.request, 'Compra general registrada exitosamente.')
        return redirect(self.success_url)


@login_required
def purchase_create(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            # Handle inline provider creation if needed, or strictly use ID.
            # Current view logic allowed 'provider' as name string or ID?
            # View used: provider_name = request.POST.get('provider') -> get_or_create
            # ModelForm expect 'provider' to be a PK.
            # To keep inline creation "safe", we might need to handle it before saving or use a specific field.
            # For this iteration, let's assume standard ModelForm validation for safety.
            # If the user needs inline creation, we should add a non-model field to the form 'provider_name'.
            # BUT: let's stick to the current logic but VALIDATE the rest.
            try:
                # We can use the form to clean data, but if we have custom logic for Provider (string vs ID),
                # we might need to adjust form.
                # Let's save commit=False and fix provider.
                purchase = form.save(commit=False)
                
                # Re-implement inline logic safely if form didn't capture it (e.g. if provider field was empty)
                provider_name = request.POST.get('provider_name') # Assuming frontend sends this if new
                if not purchase.provider and provider_name:
                     purchase.provider, _ = Provider.objects.get_or_create(name=provider_name.strip(), user=request.user, defaults={'user': request.user})
                
                purchase.user = request.user
                purchase.save()
                messages.success(request, 'Compra registrada exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al registrar compra: {str(e)}')
        else:
            messages.error(request, f'Error validación: {form.errors}')
            
        return redirect(request.META.get('HTTP_REFERER', 'fixed_cost_list'))
    return redirect('fixed_cost_list')

@login_required
def variable_expense_create(request):
    if request.method == 'POST':
        form = VariableExpenseForm(request.POST)
        if form.is_valid():
            try:
                expense = form.save(commit=False)
                expense.user = request.user
                expense.cost_definition = None
                # Auto-assign month based on due_date
                expense.month = date(expense.due_date.year, expense.due_date.month, 1)
                expense.save()
                messages.success(request, 'Gasto variable registrado.')
            except Exception as e:
                messages.error(request, f'Error al registrar gasto: {str(e)}')
        else:
             messages.error(request, f'Error validación: {form.errors}')

        return redirect(request.META.get('HTTP_REFERER', 'fixed_cost_list'))
    return redirect('fixed_cost_list')

# -----------------------------------------------------------------------------
# Assets (Bienes de Uso) Views
# -----------------------------------------------------------------------------

@login_required
def asset_list(request):
    """Dashboard for Fixed Assets"""
    assets = Asset.objects.filter(user=request.user).select_related('category', 'provider').order_by('-purchase_date')
    categories = AssetCategory.objects.filter(user=request.user).order_by('name')
    providers = Provider.objects.filter(user=request.user).order_by('name')
    
    total_value = sum(asset.cost * asset.quantity for asset in assets)
    
    context = {
        'assets': assets,
        'categories': categories,
        'providers': providers,
        'total_value': total_value,
        'today': timezone.now().date(),
    }
    return render(request, 'finance/asset_list.html', context)

@login_required
def asset_create(request):
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # If user selected "+ Nueva Categoría", the value is "new", which fails ModelChoiceField validation.
        # We clear it so the form sees it as None (valid since required=False).
        # The view logic below handles creating the new category from 'new_category' input.
        if post_data.get('category') == 'new':
            post_data['category'] = ''
            
        form = AssetForm(post_data)
        # Filter querysets for isolation
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = AssetCategory.objects.filter(user=request.user)

        if form.is_valid():
            try:
                # Handle category (inline creation) and provider (inline creation)
                # Logic: form.save(commit=False). If fields are empty but 'new_category' or 'provider' name is provided, handle it.
                # Since ModelForm validation runs first, if fields are required, empty will fail.
                # Assuming simple flow for now:
                asset = form.save(commit=False)
                new_category_name = request.POST.get('new_category')
                provider_name = request.POST.get('provider_name') # Helper if form provider is empty

                # Handle Category
                if not asset.category and new_category_name:
                    asset.category, _ = AssetCategory.objects.get_or_create(
                        name=new_category_name.strip(),
                        user=request.user,
                        defaults={'user': request.user}
                    )
                
                # Handle Provider (if form field empty but name provided)
                if not asset.provider and provider_name:
                    asset.provider, _ = Provider.objects.get_or_create(
                        name=provider_name.strip(),
                        user=request.user,
                        defaults={'user': request.user}
                    )
                
                asset.user = request.user
                asset.save()
                
                # AUTOMATICALLY CREATE PURCHASE RECORD (Financial Transaction)
                # This ensures the asset purchase appears in cash flow / accounts payable
                Purchase.objects.create(
                    user=request.user,
                    date=asset.purchase_date,
                    provider=asset.provider,
                    # We might need a generic 'Activos Fijos' category or similar.
                    # For now we leave category blank or try to find one.
                    description=f"Compra de Activo Fijo: {asset.name}",
                    amount=asset.cost * asset.quantity,
                    due_date=asset.purchase_date, # Default to same day
                    payment_status='PENDING', # Default to pending, user can update
                    is_paid=False
                )
                
                messages.success(request, 'Bien de uso registrado exitosamente (y generado su movimiento de compra).')
            except Exception as e:
                messages.error(request, f'Error al registrar bien: {str(e)}')
        else:
            messages.error(request, f'Error validación: {form.errors}')
            
    else:
        form = AssetForm()
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = AssetCategory.objects.filter(user=request.user)

    return render(request, 'finance/asset_form.html', {
        'form': form,
        'today': timezone.now().date()
    })

@login_required
def asset_category_delete(request, pk):
    category = get_object_or_404(AssetCategory, pk=pk, user=request.user)
    category.delete()
    messages.success(request, 'Categoría eliminada.')
    return redirect('asset_list')

@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk, user=request.user)
    return render(request, 'finance/asset_detail.html', {'asset': asset})

@login_required
def asset_update(request, pk):
    asset = get_object_or_404(Asset, pk=pk, user=request.user)
    if request.method == 'POST':
        # Create a mutable copy of POST data to handle "new" category logic if needed,
        # mirroring the create view logic for consistency so editing doesn't break if the form is reused.
        post_data = request.POST.copy()
        if post_data.get('category') == 'new':
            post_data['category'] = ''
            
        form = AssetForm(post_data, instance=asset)
        # Filter querysets for isolation
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = AssetCategory.objects.filter(user=request.user)

        if form.is_valid():
            try:
                # Basic save first
                asset = form.save(commit=False)
                
                # Handle potentially new category from edit form if we decide to expose that
                new_category_name = request.POST.get('new_category')
                if not asset.category and new_category_name:
                    asset.category, _ = AssetCategory.objects.get_or_create(
                        name=new_category_name.strip(),
                        user=request.user,
                        defaults={'user': request.user}
                    )
                
                asset.save()
                messages.success(request, 'Bien de uso actualizado exitosamente.')
                return redirect('asset_detail', pk=asset.pk)
            except Exception as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
        else:
             messages.error(request, f'Error validación: {form.errors}')
    else:
        form = AssetForm(instance=asset)
        # Filter querysets for isolation
        form.fields['provider'].queryset = Provider.objects.filter(user=request.user)
        form.fields['category'].queryset = AssetCategory.objects.filter(user=request.user)
    
    # We need providers and categories for the form context if we use a custom template or generic form
    categories = AssetCategory.objects.filter(user=request.user).order_by('name')
    providers = Provider.objects.filter(user=request.user).order_by('name')
        
    return render(request, 'finance/asset_form.html', {
        'form': form, 
        'asset': asset,
        'categories': categories,
        'providers': providers,
        'title': f'Editar {asset.name}'
    })

# -----------------------------------------------------------------------------
# Provider Management Views
# -----------------------------------------------------------------------------

@login_required
def provider_list(request):
    providers = Provider.objects.filter(user=request.user).order_by('name')
    context = {'providers': providers}
    return render(request, 'finance/provider_list.html', context)

@login_required
def provider_create(request):
    if request.method == 'POST':
        form = ProviderForm(request.POST)
        if form.is_valid():
            provider = form.save(commit=False)
            provider.user = request.user
            provider.save()
            messages.success(request, 'Proveedor creado exitosamente.')
            return redirect('provider_list')
    else:
        form = ProviderForm()
    return render(request, 'finance/provider_form.html', {'form': form})

@login_required
def provider_update(request, pk):
    provider = get_object_or_404(Provider, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ProviderForm(request.POST, instance=provider)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado.')
            return redirect('provider_list')
    else:
        form = ProviderForm(instance=provider) # Use instance to pre-fill
        
    return render(request, 'finance/provider_form.html', {'form': form, 'provider': provider})

@login_required
def provider_detail(request, pk):
    provider = get_object_or_404(Provider, pk=pk, user=request.user)
    
    # History of Purchases (Regular expenses/purchases)
    purchases = Purchase.objects.filter(user=request.user, provider=provider).order_by('-date')
    
    # History of Assets bought from this provider
    assets = Asset.objects.filter(user=request.user, provider=provider).order_by('-purchase_date')
    
    # Calculate totals
    total_purchases = purchases.aggregate(Sum('amount'))['amount__sum'] or 0
    total_assets = assets.aggregate(Sum('cost'))['cost__sum'] or 0
    total_spent = total_purchases + total_assets
    
    context = {
        'provider': provider,
        'purchases': purchases,
        'assets': assets,
        'total_purchases': total_purchases,
        'total_assets': total_assets,
        'total_spent': total_spent,
    }
    return render(request, 'finance/provider_detail.html', context)

# -----------------------------------------------------------------------------
# Financial Dashboard Views (Phase 2)
# -----------------------------------------------------------------------------

@login_required
def cashflow_dashboard(request):
    """
    Shows Cash Flow (Money In/Out) per Account.
    """
    from django.core.paginator import Paginator

    accounts = Account.objects.filter(user=request.user, is_active=True)

    # Calculate Live Balance for each account
    total_balance = Decimal('0.00')

    for acc in accounts:
        m_qs = CashMovement.objects.filter(user=request.user, account=acc, date__gte=acc.opening_date)
        total_in = m_qs.filter(type='IN').aggregate(Sum('amount'))['amount__sum'] or 0
        total_out = m_qs.filter(type='OUT').aggregate(Sum('amount'))['amount__sum'] or 0

        acc.current_balance = acc.opening_balance + total_in - total_out
        total_balance += acc.current_balance

    # Date Filter for Movements List — dynamic default: Jan 1 of current year
    default_start = date(date.today().year, 1, 1)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    account_filter = request.GET.get('account', '')

    start_date = default_start
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            pass

    # Recent Movements Query
    movements_qs = CashMovement.objects.filter(user=request.user, date__date__gte=start_date)

    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
            movements_qs = movements_qs.filter(date__date__lte=end_date)
        except ValueError:
            pass

    if account_filter:
        movements_qs = movements_qs.filter(account_id=account_filter)

    movements_qs = movements_qs.select_related('account').order_by('-date')

    paginator = Paginator(movements_qs, 50)
    page_number = request.GET.get('page')
    movements = paginator.get_page(page_number)

    # Monthly chart data (IN vs OUT by month for current year)
    import json
    from django.db.models.functions import TruncMonth
    from django.db.models import Count

    chart_qs = CashMovement.objects.filter(
        user=request.user,
        date__date__gte=date(date.today().year, 1, 1)
    ).annotate(month=TruncMonth('date')).values('month', 'type').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('month')

    monthly_data = {}
    for row in chart_qs:
        m = row['month'].strftime('%Y-%m') if row['month'] else ''
        if m not in monthly_data:
            monthly_data[m] = {'month': m, 'in_total': 0, 'out_total': 0}
        if row['type'] == 'IN':
            monthly_data[m]['in_total'] = float(row['total'] or 0)
        else:
            monthly_data[m]['out_total'] = float(row['total'] or 0)

    cashflow_chart_data = json.dumps(list(monthly_data.values()))

    # KPIs over the *filtered* period — match what the user sees in the table.
    kpi_qs = movements_qs  # already filtered above
    kpi_in = kpi_qs.filter(type='IN').aggregate(s=Sum('amount'))['s'] or 0
    kpi_out = kpi_qs.filter(type='OUT').aggregate(s=Sum('amount'))['s'] or 0
    kpi_net = kpi_in - kpi_out
    kpi_count = kpi_qs.count()

    # Top categories by absolute amount in the filtered period.
    top_categories = list(
        kpi_qs.values('category', 'type').annotate(
            total=Sum('amount'), count=Count('id')
        ).order_by('-total')[:5]
    )

    context = {
        'accounts': accounts,
        'total_balance': total_balance,
        'movements': movements,
        'start_date': start_date.isoformat(),
        'end_date': end_date_str or '',
        'account_filter': account_filter,
        'cashflow_chart_data': cashflow_chart_data,
        'kpi_in': kpi_in,
        'kpi_out': kpi_out,
        'kpi_net': kpi_net,
        'kpi_count': kpi_count,
        'top_categories': top_categories,
    }
    return render(request, 'finance/dashboard_cashflow.html', context)

@login_required
def aging_dashboard(request):
    """Accounts Receivable + Accounts Payable with aging buckets, KPIs, top
    debtors/creditors, filters, and a net cashflow projection.

    Buckets are computed by `due_date` vs today:
        - current: not yet due
        - b_0_30:  1..30 days overdue
        - b_31_60: 31..60 days overdue
        - b_61_90: 61..90 days overdue
        - b_90:    90+ days overdue
    """
    today = timezone.now().date()
    q = (request.GET.get('q') or '').strip()
    bucket = (request.GET.get('bucket') or '').strip()
    status = (request.GET.get('status') or '').strip()  # PENDING / PARTIAL / OVERDUE / ''
    side = (request.GET.get('side') or '').strip()      # receivables / payables / ''

    # Receivables (Me deben)
    rec_qs = (Sale.objects
              .filter(user=request.user, payment_status__in=['PENDING', 'PARTIAL'])
              .exclude(status='CANCELLED')
              .select_related('customer')
              .annotate(balance_calc=F('total') - F('paid_amount'))
              .order_by('due_date', '-id'))
    if q:
        rec_qs = rec_qs.filter(
            models.Q(customer__name__icontains=q)
            | models.Q(id__iexact=q.lstrip('#'))
        )
    if status in ('PENDING', 'PARTIAL'):
        rec_qs = rec_qs.filter(payment_status=status)
    elif status == 'OVERDUE':
        rec_qs = rec_qs.filter(due_date__lt=today)

    # Payables (Debo)
    pay_qs = (Purchase.objects
              .filter(user=request.user, payment_status__in=['PENDING', 'PARTIAL'])
              .select_related('provider', 'category')
              .annotate(balance_calc=F('amount') - F('paid_amount'))
              .order_by('due_date', '-id'))
    if q:
        pay_qs = pay_qs.filter(
            models.Q(provider__name__icontains=q)
            | models.Q(category__name__icontains=q)
            | models.Q(description__icontains=q)
            | models.Q(code__icontains=q)
        )
    if status in ('PENDING', 'PARTIAL'):
        pay_qs = pay_qs.filter(payment_status=status)
    elif status == 'OVERDUE':
        pay_qs = pay_qs.filter(due_date__lt=today)

    def _bucket(due, today_):
        if not due:
            return 'no_date'
        if due >= today_:
            return 'current'
        days = (today_ - due).days
        if days <= 30:
            return 'b_0_30'
        if days <= 60:
            return 'b_31_60'
        if days <= 90:
            return 'b_61_90'
        return 'b_90'

    def _build_buckets(items):
        buckets = {'current': [], 'b_0_30': [], 'b_31_60': [], 'b_61_90': [], 'b_90': [], 'no_date': []}
        for it in items:
            buckets[_bucket(it.due_date, today)].append(it)
        return buckets

    receivables_list = list(rec_qs)
    payables_list = list(pay_qs)

    rec_buckets = _build_buckets(receivables_list)
    pay_buckets = _build_buckets(payables_list)

    if bucket and bucket in rec_buckets:
        receivables_list = rec_buckets[bucket]
    if bucket and bucket in pay_buckets:
        payables_list = pay_buckets[bucket]

    def _sum_balance(items):
        return sum((i.balance_calc or 0) for i in items)

    rec_bucket_totals = {k: {'count': len(v), 'amount': _sum_balance(v)} for k, v in rec_buckets.items()}
    pay_bucket_totals = {k: {'count': len(v), 'amount': _sum_balance(v)} for k, v in pay_buckets.items()}

    total_receivables = sum(v['amount'] for v in rec_bucket_totals.values())
    total_payables = sum(v['amount'] for v in pay_bucket_totals.values())

    # Ordered, template-friendly bucket rows with precomputed % bar widths.
    BUCKET_ORDER = [
        ('current', 'Vigente', 'emerald'),
        ('b_0_30', '1–30 días', 'amber'),
        ('b_31_60', '31–60 días', 'orange'),
        ('b_61_90', '61–90 días', 'rose'),
        ('b_90', '+90 días', 'red'),
        ('no_date', 'Sin fecha', 'slate'),
    ]

    def _make_rows(totals_map, total):
        rows = []
        for key, label, color in BUCKET_ORDER:
            d = totals_map.get(key, {'count': 0, 'amount': 0})
            amount = d['amount']
            pct = int((amount / total) * 100) if total and total > 0 else 0
            rows.append({
                'key': key, 'label': label, 'color': color,
                'count': d['count'], 'amount': amount, 'pct': pct,
            })
        return rows

    rec_bucket_rows = _make_rows(rec_bucket_totals, total_receivables)
    pay_bucket_rows = _make_rows(pay_bucket_totals, total_payables)
    net_position = total_receivables - total_payables

    overdue_rec_amount = sum(v['amount'] for k, v in rec_bucket_totals.items() if k.startswith('b_'))
    overdue_pay_amount = sum(v['amount'] for k, v in pay_bucket_totals.items() if k.startswith('b_'))
    overdue_rec_count = sum(v['count'] for k, v in rec_bucket_totals.items() if k.startswith('b_'))
    overdue_pay_count = sum(v['count'] for k, v in pay_bucket_totals.items() if k.startswith('b_'))

    # Top debtors/creditors (Top 5 by outstanding balance).
    top_debtors = {}
    for s in rec_qs:
        key = s.customer_id or 0
        name = s.customer.name if s.customer_id else 'Consumidor Final'
        d = top_debtors.setdefault(key, {'name': name, 'amount': 0, 'count': 0, 'overdue': 0})
        d['amount'] += s.balance_calc or 0
        d['count'] += 1
        if s.due_date and s.due_date < today:
            d['overdue'] += s.balance_calc or 0
    top_debtors = sorted(top_debtors.values(), key=lambda x: -x['amount'])[:5]

    top_creditors = {}
    for p in pay_qs:
        key = p.provider_id or 0
        name = p.provider.name if p.provider_id else (p.category.name if p.category_id else 'Sin proveedor')
        d = top_creditors.setdefault(key, {'name': name, 'amount': 0, 'count': 0, 'overdue': 0})
        d['amount'] += p.balance_calc or 0
        d['count'] += 1
        if p.due_date and p.due_date < today:
            d['overdue'] += p.balance_calc or 0
    top_creditors = sorted(top_creditors.values(), key=lambda x: -x['amount'])[:5]

    # Cashflow forecast (next 30 / 60 / 90 days inflow vs outflow).
    horizons = [7, 30, 60, 90]
    forecast = []
    for days in horizons:
        cutoff = today + timedelta(days=days)
        inflow = sum((s.balance_calc or 0) for s in rec_qs if s.due_date and s.due_date <= cutoff)
        outflow = sum((p.balance_calc or 0) for p in pay_qs if p.due_date and p.due_date <= cutoff)
        forecast.append({'days': days, 'inflow': inflow, 'outflow': outflow, 'net': inflow - outflow})

    context = {
        'today': today,
        'q': q,
        'bucket': bucket,
        'status': status,
        'side': side,
        'receivables': receivables_list,
        'payables': payables_list,
        'rec_bucket_totals': rec_bucket_totals,
        'pay_bucket_totals': pay_bucket_totals,
        'rec_bucket_rows': rec_bucket_rows,
        'pay_bucket_rows': pay_bucket_rows,
        'total_receivables': total_receivables,
        'total_payables': total_payables,
        'net_position': net_position,
        'overdue_rec_amount': overdue_rec_amount,
        'overdue_pay_amount': overdue_pay_amount,
        'overdue_rec_count': overdue_rec_count,
        'overdue_pay_count': overdue_pay_count,
        'top_debtors': top_debtors,
        'top_creditors': top_creditors,
        'forecast': forecast,
    }
    return render(request, 'finance/dashboard_aging.html', context)

@login_required
def import_transactions(request):
    """
    Upload CSV (Mercado Pago / Bank) to import CashMovements.

    Renders summary stats and history of recent imports for context.
    """
    last_stats = None
    if request.method == 'POST':
        form = TransactionImportForm(request.POST, request.FILES)
        if form.is_valid():
            f = request.FILES['file']
            importer = MercadoPagoCashImporter(request.user)
            stats = importer.process_file(f)

            if 'error' in stats:
                messages.error(request, stats['error'])
                last_stats = {'error': stats['error']}
            else:
                created = stats.get('created', 0)
                duplicates = stats.get('duplicates', 0)
                errors = stats.get('errors', 0)
                last_stats = {'created': created, 'duplicates': duplicates, 'errors': errors,
                              'filename': getattr(f, 'name', '')}
                if created or duplicates or errors:
                    messages.success(
                        request,
                        f"Importación completa: {created} creados, {duplicates} duplicados, {errors} errores."
                    )
                else:
                    messages.warning(request, 'El archivo no produjo movimientos nuevos.')
                # Stay on page so user sees the result card.
        else:
            messages.error(request, 'Revisa el formulario.')
    else:
        form = TransactionImportForm()

    # Show last 10 imported movements as a quick sanity check.
    recent_imports = CashMovement.objects.filter(
        user=request.user,
        external_id__isnull=False,
    ).exclude(external_id='').select_related('account').order_by('-created_at')[:10]

    accounts_count = Account.objects.filter(user=request.user, is_active=True).count()

    return render(request, 'finance/import_form.html', {
        'form': form,
        'last_stats': last_stats,
        'recent_imports': recent_imports,
        'accounts_count': accounts_count,
    })



@login_required
def account_create_popup(request):
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            return JsonResponse({
                'status': 'success',
                'id': account.id,
                'name': str(account)
            })
        else:
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            }, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@login_required
def provider_detail_api(request, pk):
    """API to get provider details for auto-filling purchase forms."""
    provider = get_object_or_404(Provider, pk=pk, user=request.user)
    
    # Get most common category from past purchases
    common_category = Purchase.objects.filter(
        provider=provider,
        user=request.user
    ).values('category__name').annotate(
        count=models.Count('id')
    ).order_by('-count').first()
    
    # Get average payment terms
    avg_days = Purchase.objects.filter(
        provider=provider,
        user=request.user,
        due_date__isnull=False
    ).annotate(
        days_diff=F('due_date') - F('date')
    ).aggregate(avg=Avg('days_diff'))
    
    # Calculate suggested due_date
    suggested_due_date = None
    if avg_days['avg']:
        suggested_due_date = (date.today() + avg_days['avg']).isoformat()
    elif hasattr(provider, 'credit_days') and provider.credit_days:
        suggested_due_date = (date.today() + timedelta(days=provider.credit_days)).isoformat()
    
    data = {
        'id': provider.id,
        'name': provider.name,
        'email': provider.email or '',
        'phone': provider.phone or '',
        'common_category': common_category['category__name'] if common_category else None,
        'suggested_due_date': suggested_due_date,
        'total_purchases': Purchase.objects.filter(provider=provider, user=request.user).count()
    }
    return JsonResponse(data)

@login_required
def account_balance_api(request, pk):
    """API to get current account balance for displaying in forms."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    
    data = {
        'id': account.id,
        'name': account.name,
        'type': account.type,
        'balance': float(account.balance),
        'currency': account.currency
    }
    return JsonResponse(data)


# ===== PHASE 8: FINANCE ADVANCED AUTOMATIONS =====

@login_required
def purchase_price_history_api(request, provider_id):
    """API to get last 3 purchase prices from a provider."""
    recent_purchases = Purchase.objects.filter(
        provider_id=provider_id,
        user=request.user
    ).order_by('-date')[:3]
    
    history = []
    for purchase in recent_purchases:
        history.append({
            'date': purchase.date.strftime('%Y-%m-%d'),
            'amount': float(purchase.amount),
            'description': purchase.description,
            'category': purchase.category.name if purchase.category else None
        })
    
    return JsonResponse({'history': history})


@login_required
def suggest_provider_by_category_api(request, category_id):
    """API to suggest providers based on purchase category."""
    # Find providers who frequently sell this category
    top_providers = Purchase.objects.filter(
        category_id=category_id,
        user=request.user
    ).values('provider__id', 'provider__name').annotate(
        purchase_count=Count('id')
    ).order_by('-purchase_count')[:5]
    
    suggestions = [
        {'id': p['provider__id'], 'name': p['provider__name'], 'count': p['purchase_count']}
        for p in top_providers
    ]
    
    return JsonResponse({'suggestions': suggestions})
