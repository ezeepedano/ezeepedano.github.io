
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView, CreateView
from django.urls import reverse_lazy
from decimal import Decimal
from datetime import date, timedelta
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Avg, Count, F
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
    """Dashboard view for finance."""
    today = timezone.now().date()
    view_year = request.GET.get('year')
    view_year = int(view_year) if view_year else today.year
    view_month = request.GET.get('month')
    view_month = int(view_month) if view_month else today.month
    
    context = FinanceReportService.get_dashboard_context(view_year, view_month, request.user)
    
    # Add extra context if needed (e.g. Purchase Categories/Providers for dropdowns)
    context['purchase_categories'] = PurchaseCategory.objects.filter(user=request.user)
    context['providers'] = Provider.objects.filter(user=request.user)
    context['view_year'] = view_year
    context['view_month'] = view_month
    
    # Re-apply filters if any (logic for filtering purchases specifically could stay in view or move to service if complex)
    # The current service returns ALL purchases for the month. Filtering by category was in the original view.
    # Let's apply it here or update service. Service returns queryset, so we can filter.
    # Filter Purchases
    purchase_category_id = request.GET.get('purchase_category')
    selected_category_id = None
    
    if purchase_category_id:
        try:
            selected_category_id = int(purchase_category_id)
            context['purchases'] = context['purchases'].filter(category_id=selected_category_id)
            # Recalculate total if filtered
            context['total_purchase_amount'] = context['purchases'].aggregate(Sum('amount'))['amount__sum'] or 0
        except (ValueError, TypeError):
            selected_category_id = None
            
    context['selected_category_id'] = selected_category_id

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
    template_name = 'finance/purchase_hub.html'

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

    context = {
        'accounts': accounts,
        'total_balance': total_balance,
        'movements': movements,
        'start_date': start_date.isoformat(),
        'end_date': end_date_str or '',
        'account_filter': account_filter,
        'cashflow_chart_data': cashflow_chart_data,
    }
    return render(request, 'finance/dashboard_cashflow.html', context)

@login_required
def aging_dashboard(request):
    """
    Shows Accounts Receivable (Sales) and Accounts Payable (Purchases).
    """
    # Receivables (Me deben)
    receivables = Sale.objects.filter(
        user=request.user, 
        payment_status__in=['PENDING', 'PARTIAL']
    ).exclude(status='CANCELLED').order_by('due_date')
    
    total_receivables = sum(r.balance for r in receivables)
    
    # Payables (Debo)
    payables = Purchase.objects.filter(
        user=request.user, 
        payment_status__in=['PENDING', 'PARTIAL']
    ).order_by('due_date')
    
    total_payables = sum(p.balance for p in payables)
    
    context = {
        'receivables': receivables,
        'payables': payables,
        'total_receivables': total_receivables,
        'total_payables': total_payables,
        'today': timezone.now().date(),
    }
    return render(request, 'finance/dashboard_aging.html', context)

@login_required
def import_transactions(request):
    """
    Upload CSV (Mercado Pago / Bank) to import CashMovements.
    """
    if request.method == 'POST':
        form = TransactionImportForm(request.POST, request.FILES)
        if form.is_valid():
            f = request.FILES['file']
            # We currently hardcode MP Importer for this version, 
            # later we can select importer strategy based on Account Type.
            importer = MercadoPagoCashImporter(request.user)
            
            # Importer processes the file
            stats = importer.process_file(f)
            
            if 'error' in stats:
                messages.error(request, stats['error'])
            else:
                messages.success(request, f"Importación completa: {stats['created']} creados, {stats['duplicates']} duplicados, {stats['errors']} errores.")
                return redirect('cashflow_dashboard')
    else:
        form = TransactionImportForm()
        
    return render(request, 'finance/import_form.html', {'form': form})



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
