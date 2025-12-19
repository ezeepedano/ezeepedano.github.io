
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import FixedCost, MonthlyExpense, Purchase, Provider, PurchaseCategory, Asset, AssetCategory
from .forms import FixedCostForm, PurchaseForm, VariableExpenseForm, AssetForm, ProviderForm
from .services import FinanceReportService, ExpenseService

@login_required
def fixed_cost_list(request):
    """Dashboard view for finance."""
    today = timezone.now().date()
    view_year = int(request.GET.get('year', today.year))
    view_month = int(request.GET.get('month', today.month))
    
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
        year = int(request.POST.get('year', timezone.now().year))
        month = int(request.POST.get('month', timezone.now().month))
        
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
                messages.success(request, 'Bien de uso registrado exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al registrar bien: {str(e)}')
        else:
            messages.error(request, f'Error validación: {form.errors}')
            
    return redirect('asset_list')

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
