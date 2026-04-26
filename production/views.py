from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db import transaction
from .models import ProductionOrder, BillOfMaterial
from .forms import ProductionOrderForm, BillOfMaterialForm, BomLineFormSet
from inventory.models import Product, Ingredient
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages

# --- Production Orders ---

class ProductionOrderListView(LoginRequiredMixin, ListView):
    model = ProductionOrder
    template_name = 'production/order_list.html'
    context_object_name = 'orders'
    ordering = ['-created_at']

    ordering = ['-created_at']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ProductionOrder.objects.filter(user=self.request.user)
        context['stats'] = {
            'total': qs.count(),
            'draft': qs.filter(status='DRAFT').count(),
            'in_progress': qs.filter(status='IN_PROGRESS').count(),
            'done': qs.filter(status='DONE').count(),
            'cancelled': qs.filter(status='CANCELLED').count(),
        }
        context['current_status'] = self.request.GET.get('status', 'ALL')
        return context

    def get_queryset(self):
        qs = ProductionOrder.objects.filter(user=self.request.user).order_by('-created_at')
        status = self.request.GET.get('status')
        if status and status != 'ALL':
            qs = qs.filter(status=status)
        return qs

class ProductionOrderCreateView(LoginRequiredMixin, CreateView):
    model = ProductionOrder
    form_class = ProductionOrderForm
    template_name = 'production/order_form.html'
    success_url = reverse_lazy('production_order_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['product'].queryset = Product.objects.filter(user=self.request.user)
        form.fields['bom'].queryset = BillOfMaterial.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        # Assign current user as creator
        form.instance.user = self.request.user

        # Generate unique code per-user: PO-{ID}
        # Both the count and the collision check are scoped to the
        # current user so codes don't leak how many orders other
        # tenants have, and they remain unique within the tenant.
        user_qs = ProductionOrder.objects.filter(user=self.request.user)
        last = user_qs.count() + 1
        code = f"PO-{last:05d}"
        while user_qs.filter(code=code).exists():
            last += 1
            code = f"PO-{last:05d}"

        form.instance.code = code

        return super().form_valid(form)

class ProductionOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductionOrder
    form_class = ProductionOrderForm
    template_name = 'production/order_form.html'
    success_url = reverse_lazy('production_order_list')

    def get_queryset(self):
        # Tenant scope: a user can only edit their own production orders.
        return ProductionOrder.objects.filter(user=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['product'].queryset = Product.objects.filter(user=self.request.user)
        form.fields['bom'].queryset = BillOfMaterial.objects.filter(user=self.request.user)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Lock ONLY if the status in the DATABASE is actually DONE/COMPLETED.
        # We query the DB specifically because self.object.status might be 
        # tentatively set to 'DONE' by the invalid form submission in memory.
        current_db_status = ProductionOrder.objects.filter(pk=self.object.pk, user=self.request.user).values_list('status', flat=True).first()
        context['locked'] = current_db_status in ['DONE', 'COMPLETED']
        return context

    def form_valid(self, form):
        # If status is changing to DONE (or is DONE) and no batch exists, try to register production
        if form.cleaned_data.get('status') == 'DONE':
            if not self.object.batches.exists():
                from traceability.services import ProductionService
                from django.core.exceptions import ValidationError
                from datetime import date
                
                try:
                    # Attempt to perform traceability transaction BEFORE saving status
                    # accurate quantity: use form data
                    qty = form.cleaned_data.get('quantity_to_produce')
                    code = self.object.code
                    internal_lot_code = f"LOT-{code}"
                    
                    # Call service
                    # Note: We pass the object instance. Since it's not saved yet with new data,
                    # we must rely on arguments passed to service for quantity/dates.
                    # The service uses 'production_order' to link FK. That works because PK exists.
                    
                    ProductionService.register_production(
                        product=form.cleaned_data.get('product'), # Use form product in case it changed
                        bom=form.cleaned_data.get('bom'),
                        quantity_produced=qty,
                        internal_lot_code=internal_lot_code,
                        user=self.request.user,
                        notes=f"Generado automáticamente desde Orden {code}",
                        production_date=form.cleaned_data.get('end_date') or date.today(),
                        production_order=self.object
                    )
                    # If successful, logic continues to super().save() which sets status=DONE
                    # The signal will fire, see batch exists, and do nothing.
                    
                except ValidationError as e:
                    # Catch traceability errors (missing stock, etc) and show to user
                    form.add_error(None, f"No se pudo finalizar la orden: {e.message}")
                    return self.form_invalid(form)
                except Exception as e:
                    form.add_error(None, f"Error inesperado al procesar producción: {str(e)}")
                    return self.form_invalid(form)

        return super().form_valid(form)

@login_required
def get_boms_for_product(request):
    product_id = request.GET.get('product_id')
    if product_id:
        boms = BillOfMaterial.objects.filter(products__id=product_id, is_active=True, user=request.user)
        data = [{'id': b.id, 'name': str(b)} for b in boms]
        return JsonResponse({'boms': data})
    return JsonResponse({'boms': []})

@login_required
def bom_detail_api(request, pk):
    """API to get BOM details including calculated cost for frontend."""
    from django.shortcuts import get_object_or_404
    bom = get_object_or_404(BillOfMaterial, pk=pk, user=request.user)
   
    # Calculate cost using existing method
    total_cost = bom.calculate_cost()
    
   # Get ingredient details
    ingredients = []
    for line in bom.lines.all():
        ing_data = {
            'name': line.ingredient.name if line.ingredient else (line.component_product.name if line.component_product else 'Unknown'),
            'quantity': float(line.quantity),
            'unit': line.ingredient.unit if line.ingredient else 'u',
        }
        ingredients.append(ing_data)
    
    data = {
        'id': bom.id,
        'name': bom.name,
        'total_cost': float(total_cost),
        'ingredients': ingredients,
        'ingredient_count': len(ingredients)
    }
    return JsonResponse(data)


# ===== PHASE 6: PRODUCTION ADVANCED AUTOMATIONS =====

@login_required
def stock_validation_api(request, bom_id):
    """API to validate if there's enough stock to produce with given BOM."""
    from django.shortcuts import get_object_or_404
    
    bom = get_object_or_404(BillOfMaterial, pk=bom_id, user=request.user)
    quantity = int(request.GET.get('quantity', 1))
    
    validation_results = []
    all_sufficient = True
    
    for line in bom.lines.all():
        if line.ingredient:
            # Calculate needed quantity
            if line.ingredient.type == 'supply':
                needed = line.quantity * quantity
            else:
                # Raw material
                percentage = line.quantity
                bom_qty = bom.quantity if bom.quantity > 0 else 1
                kg_per_unit = (percentage / 100) * bom_qty
                needed = kg_per_unit * quantity
            
            available = line.ingredient.stock_quantity
            sufficient = available >= needed
            
            if not sufficient:
                all_sufficient = False
            
            validation_results.append({
                'ingredient': line.ingredient.name,
                'needed': float(needed),
                'available': float(available),
                'unit': line.ingredient.unit,
                'sufficient': sufficient
            })
    
    return JsonResponse({
        'all_sufficient': all_sufficient,
        'results': validation_results
    })

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

@login_required
@require_POST
def bulk_delete_orders(request):
    order_ids = request.POST.getlist('order_ids')
    if order_ids:
        try:
            orders = ProductionOrder.objects.filter(id__in=order_ids, user=request.user)
            count = orders.count()
            orders.delete()
            messages.success(request, f"Se eliminaron {count} órdenes correctamente.")
        except Exception as e:
            messages.error(request, f"Error al eliminar órdenes: {e}")
    else:
        messages.warning(request, "No se seleccionaron órdenes para eliminar.")
    
    return redirect('production_order_list')


# --- Formulas (BOMs) ---

class BillOfMaterialListView(LoginRequiredMixin, ListView):
    model = BillOfMaterial
    template_name = 'production/bom_list.html'
    context_object_name = 'boms'

    def get_queryset(self):
        return BillOfMaterial.objects.filter(user=self.request.user).order_by('name')

class BillOfMaterialCreateView(LoginRequiredMixin, CreateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['products'].queryset = Product.objects.filter(user=self.request.user)
        return form

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            formset = BomLineFormSet(self.request.POST)
        else:
            formset = BomLineFormSet()
        
        for form in formset.forms:
            form.fields['ingredient'].queryset = Ingredient.objects.filter(user=self.request.user)
        
        empty_form = formset.empty_form
        empty_form.fields['ingredient'].queryset = Ingredient.objects.filter(user=self.request.user)
        
        data['lines'] = formset
        data['empty_form'] = empty_form
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context['lines']
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.user = self.request.user
            self.object.save()
            # Save M2M
            form.save_m2m() 
            
            if lines.is_valid():
                lines.instance = self.object
                lines.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)

class BillOfMaterialUpdateView(LoginRequiredMixin, UpdateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_queryset(self):
        # Tenant scope: a user can only edit their own BOMs.
        return BillOfMaterial.objects.filter(user=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['products'].queryset = Product.objects.filter(user=self.request.user)
        return form

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            formset = BomLineFormSet(self.request.POST, instance=self.object)
        else:
            formset = BomLineFormSet(instance=self.object)
            
        for form in formset.forms:
            form.fields['ingredient'].queryset = Ingredient.objects.filter(user=self.request.user)
        
        empty_form = formset.empty_form
        empty_form.fields['ingredient'].queryset = Ingredient.objects.filter(user=self.request.user)
        
        data['lines'] = formset
        data['empty_form'] = empty_form
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context['lines']
        with transaction.atomic():
            self.object = form.save()
            if lines.is_valid():
                lines.instance = self.object
                lines.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)

@login_required
@require_POST
def bulk_delete_boms(request):
    bom_ids = request.POST.getlist('bom_ids')
    if bom_ids:
        try:
            boms = BillOfMaterial.objects.filter(id__in=bom_ids, user=request.user)
            count = boms.count()
            boms.delete()
            messages.success(request, f"Se eliminaron {count} fórmulas correctamente.")
        except Exception as e:
            messages.error(request, f"Error al eliminar fórmulas: {e}")
    else:
        messages.warning(request, "No se seleccionaron fórmulas para eliminar.")
    
    return redirect('bom_list')


# --- Work In Process (WIP) Stock ---

@login_required
def wip_stock_list(request):
    """List all WIP stock entries grouped by stage with summary stats."""
    from .models import WorkInProcessStock
    from .forms import WorkInProcessStockForm
    from django.db.models import Sum, Count
    from decimal import Decimal

    wip_items = WorkInProcessStock.objects.filter(user=request.user).select_related('product')
    mixed_items = wip_items.filter(stage='MIXED')
    packaged_items = wip_items.filter(stage='PACKAGED')

    # Stats
    mixed_stats = mixed_items.aggregate(
        count=Count('id'),
        total_qty=Sum('quantity'),
    )
    packaged_stats = packaged_items.aggregate(
        count=Count('id'),
        total_qty=Sum('quantity'),
    )

    # Count distinct products in WIP
    distinct_products = wip_items.values('product').distinct().count()

    # Finished product stock for context
    finished_stock = Product.objects.filter(
        user=request.user, stock_quantity__gt=0
    ).aggregate(count=Count('id'))['count'] or 0

    # Provide empty form for adding new entries
    form = WorkInProcessStockForm()
    form.fields['product'].queryset = Product.objects.filter(user=request.user)

    return render(request, 'production/wip_stock.html', {
        'mixed_items': mixed_items,
        'packaged_items': packaged_items,
        'form': form,
        'stats': {
            'mixed_count': mixed_stats['count'] or 0,
            'mixed_qty': mixed_stats['total_qty'] or Decimal('0'),
            'packaged_count': packaged_stats['count'] or 0,
            'packaged_qty': packaged_stats['total_qty'] or Decimal('0'),
            'total_wip': (mixed_stats['count'] or 0) + (packaged_stats['count'] or 0),
            'distinct_products': distinct_products,
            'finished_stock': finished_stock,
        },
    })


@login_required
@require_POST
def wip_stock_save(request):
    """Create or update a WIP stock entry."""
    from .models import WorkInProcessStock
    from .forms import WorkInProcessStockForm

    pk = request.POST.get('pk')

    if pk:
        # Update existing
        instance = get_object_or_404(WorkInProcessStock, pk=pk, user=request.user)
        form = WorkInProcessStockForm(request.POST, instance=instance)
    else:
        # Create new
        form = WorkInProcessStockForm(request.POST)

    form.fields['product'].queryset = Product.objects.filter(user=request.user)

    if form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.save()
        messages.success(request, "Stock en proceso actualizado correctamente.")
    else:
        messages.error(request, "Error al guardar. Verifica los datos ingresados.")

    return redirect('wip_stock_list')


@login_required
@require_POST
def wip_stock_delete(request, pk):
    """Delete a WIP stock entry."""
    from .models import WorkInProcessStock
    obj = get_object_or_404(WorkInProcessStock, pk=pk, user=request.user)
    obj.delete()
    messages.success(request, "Registro eliminado correctamente.")
    return redirect('wip_stock_list')
