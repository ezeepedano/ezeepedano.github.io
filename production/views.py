from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import (
    ProductionOrder, BillOfMaterial, BomLine, WorkInProcessStock,
    CompanyConfig, ProductSpecification, QualityResult,
)
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
        context['current_search'] = self.request.GET.get('q', '')
        context['current_from'] = self.request.GET.get('from', '')
        context['current_to'] = self.request.GET.get('to', '')

        # Annotate orders with batch count for "Sin batch" badge
        annotated = list(
            self.get_queryset()
            .select_related('product', 'bom')
            .annotate(batch_count=Count('batches'))
        )
        today = timezone.localdate()
        for o in annotated:
            o.days_since_creation = (today - o.created_at.date()).days if o.created_at else 0
            o.missing_batch = (o.status == 'DONE' and o.batch_count == 0)
        context['orders'] = annotated
        return context

    def get_queryset(self):
        qs = ProductionOrder.objects.filter(user=self.request.user).order_by('-created_at')
        status = self.request.GET.get('status')
        if status and status != 'ALL':
            qs = qs.filter(status=status)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(code__icontains=q) | Q(product__name__icontains=q) | Q(origin__icontains=q)
            )
        d_from = self.request.GET.get('from')
        d_to = self.request.GET.get('to')
        if d_from:
            qs = qs.filter(created_at__date__gte=d_from)
        if d_to:
            qs = qs.filter(created_at__date__lte=d_to)
        return qs

class ProductionOrderCreateView(LoginRequiredMixin, CreateView):
    model = ProductionOrder
    form_class = ProductionOrderForm
    template_name = 'production/order_form.html'
    success_url = reverse_lazy('production_order_list')

    def get_initial(self):
        initial = super().get_initial()
        product_id = self.request.GET.get('product')
        bom_id = self.request.GET.get('bom')
        origin = self.request.GET.get('origin')
        if product_id:
            try:
                p = Product.objects.filter(user=self.request.user, pk=product_id).first()
                if p:
                    initial['product'] = p
                    # Suggest gap qty
                    gap = (p.min_stock or 0) - (p.stock_quantity or 0)
                    if gap > 0:
                        initial['quantity_to_produce'] = gap
            except Exception:
                pass
        if bom_id:
            try:
                b = BillOfMaterial.objects.filter(user=self.request.user, pk=bom_id).first()
                if b:
                    initial['bom'] = b
            except Exception:
                pass
        if origin:
            initial['origin'] = origin
        return initial

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
        qs = BillOfMaterial.objects.filter(user=self.request.user).order_by('name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        active = self.request.GET.get('active')
        if active == '1':
            qs = qs.filter(is_active=True)
        elif active == '0':
            qs = qs.filter(is_active=False)
        return qs.prefetch_related('lines', 'lines__ingredient', 'lines__component_product', 'products')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_qs = BillOfMaterial.objects.filter(user=self.request.user)
        active_count = all_qs.filter(is_active=True).count()
        inactive_count = all_qs.filter(is_active=False).count()

        # Decorate each bom with cost/lines/products counts
        boms = list(context['boms'])
        total_cost = Decimal('0')
        total_lines = 0
        for bom in boms:
            try:
                bom.cost_preview = bom.calculate_cost() or Decimal('0')
            except Exception:
                bom.cost_preview = Decimal('0')
            bom.line_count = bom.lines.count()
            bom.product_count = bom.products.count()
            total_cost += Decimal(bom.cost_preview)
            total_lines += bom.line_count
        avg_cost = (total_cost / len(boms)) if boms else Decimal('0')

        context['stats'] = {
            'total': all_qs.count(),
            'active': active_count,
            'inactive': inactive_count,
            'avg_cost': avg_cost,
            'total_lines': total_lines,
        }
        context['current_search'] = self.request.GET.get('q', '')
        context['current_active'] = self.request.GET.get('active', '')
        return context

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
    mixed_qs = wip_items.filter(stage='MIXED')
    packaged_qs = wip_items.filter(stage='PACKAGED')

    # Stats
    mixed_stats = mixed_qs.aggregate(
        count=Count('id'),
        total_qty=Sum('quantity'),
    )
    packaged_stats = packaged_qs.aggregate(
        count=Count('id'),
        total_qty=Sum('quantity'),
    )

    # Materialize and add age decoration
    today = timezone.localdate()
    mixed_items = list(mixed_qs)
    packaged_items = list(packaged_qs)
    stale_count = 0
    for it in mixed_items + packaged_items:
        it.age_days = (today - it.created_at.date()).days if it.created_at else 0
        it.is_stale = it.age_days > 14
        if it.is_stale:
            stale_count += 1

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
            'stale_count': stale_count,
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


# ===== PRODUCTION HUB / DASHBOARD =====

@login_required
def production_hub(request):
    """
    Central production dashboard. Shows KPIs, MRP suggestions, BPM/ISO
    compliance alerts and recent activity. Tenant-scoped.
    """
    from traceability.models import ProductionBatch
    from inventory.models import Batch as InventoryBatch

    user = request.user
    today = timezone.localdate()
    month_start = today.replace(day=1)

    # Base querysets
    orders_qs = ProductionOrder.objects.filter(user=user)
    boms_qs = BillOfMaterial.objects.filter(user=user)
    wip_qs = WorkInProcessStock.objects.filter(user=user)
    products_qs = Product.objects.filter(user=user)
    batches_qs = ProductionBatch.objects.filter(user=user)

    # KPIs
    kpis = {
        'orders_total': orders_qs.count(),
        'orders_draft': orders_qs.filter(status='DRAFT').count(),
        'orders_in_progress': orders_qs.filter(status='IN_PROGRESS').count(),
        'orders_done': orders_qs.filter(status='DONE').count(),
        'orders_cancelled': orders_qs.filter(status='CANCELLED').count(),
        'boms_active': boms_qs.filter(is_active=True).count(),
        'boms_inactive': boms_qs.filter(is_active=False).count(),
        'wip_items': wip_qs.count(),
        'wip_qty': wip_qs.aggregate(t=Coalesce(Sum('quantity'), Value(Decimal('0'))))['t'],
        'batches_month': batches_qs.filter(production_date__gte=month_start).count(),
        'batches_total': batches_qs.count(),
    }

    # Products needing production (low stock, has at least one active BOM)
    low_stock_products = products_qs.filter(
        Q(stock_quantity__lte=F('min_stock')) | Q(stock_quantity__lte=5)
    ).order_by('stock_quantity')[:30]

    mrp_suggestions = []
    for prod in low_stock_products:
        bom = boms_qs.filter(is_active=True, products=prod).first()
        if bom:
            mrp_suggestions.append({
                'product': prod,
                'bom': bom,
                'gap': max((prod.min_stock or 0) - (prod.stock_quantity or 0), 1),
            })
    mrp_suggestions = mrp_suggestions[:10]

    kpis['mrp_count'] = len(mrp_suggestions)

    # BPM compliance signals
    # Batches missing quality results
    batches_without_quality = batches_qs.annotate(
        qr_count=Count('quality_results')
    ).filter(qr_count=0)
    # Orders DONE without batch
    orders_done_no_batch = orders_qs.filter(status='DONE').annotate(
        b_count=Count('batches')
    ).filter(b_count=0)
    # Expiring inventory batches (next 30 days) — using inventory.Batch.expiration_date
    soon = today + timedelta(days=30)
    expiring_batches = InventoryBatch.objects.filter(
        user=user,
        expiration_date__isnull=False,
        expiration_date__gte=today,
        expiration_date__lte=soon,
    ).select_related('ingredient', 'product').order_by('expiration_date')[:10]
    expired_batches = InventoryBatch.objects.filter(
        user=user,
        expiration_date__isnull=False,
        expiration_date__lt=today,
    ).select_related('ingredient', 'product').order_by('expiration_date')[:10]

    compliance = {
        'batches_no_quality': batches_without_quality.count(),
        'batches_no_quality_list': batches_without_quality.select_related('product')[:5],
        'orders_done_no_batch': orders_done_no_batch.count(),
        'orders_done_no_batch_list': orders_done_no_batch.select_related('product')[:5],
        'expiring_count': expiring_batches.count(),
        'expiring_list': expiring_batches,
        'expired_count': expired_batches.count(),
        'expired_list': expired_batches,
    }

    # Recent activity
    recent_orders = orders_qs.select_related('product').order_by('-created_at')[:10]
    recent_batches = batches_qs.select_related('product').order_by('-production_date', '-id')[:10]

    # Company config for header
    try:
        config = CompanyConfig.get_config()
    except Exception:
        config = None

    # WIP grouping for tile
    wip_mixed = wip_qs.filter(stage='MIXED').aggregate(c=Count('id'))['c'] or 0
    wip_packaged = wip_qs.filter(stage='PACKAGED').aggregate(c=Count('id'))['c'] or 0
    kpis['wip_mixed'] = wip_mixed
    kpis['wip_packaged'] = wip_packaged

    return render(request, 'production/hub.html', {
        'kpis': kpis,
        'mrp_suggestions': mrp_suggestions,
        'compliance': compliance,
        'recent_orders': recent_orders,
        'recent_batches': recent_batches,
        'config': config,
        'today': today,
    })


# ===== BPM/ISO COMPLIANCE DASHBOARD =====

@login_required
def compliance_dashboard(request):
    """
    BPM / ISO 9001 compliance dashboard:
    - Batches without quality results
    - Orders DONE without batch (broken automation)
    - Expiring / expired inventory batches
    - Recent status change audit trail
    """
    from traceability.models import ProductionBatch
    from inventory.models import Batch as InventoryBatch

    user = request.user
    today = timezone.localdate()

    batches_no_quality = ProductionBatch.objects.filter(user=user).annotate(
        qr_count=Count('quality_results')
    ).filter(qr_count=0).select_related('product').order_by('-production_date')

    orders_done_no_batch = ProductionOrder.objects.filter(
        user=user, status='DONE'
    ).annotate(b_count=Count('batches')).filter(b_count=0).select_related('product', 'bom')

    soon_30 = today + timedelta(days=30)
    soon_60 = today + timedelta(days=60)
    soon_90 = today + timedelta(days=90)

    expiring_30 = InventoryBatch.objects.filter(
        user=user, expiration_date__isnull=False,
        expiration_date__gte=today, expiration_date__lte=soon_30,
    ).select_related('ingredient', 'product').order_by('expiration_date')
    expiring_60 = InventoryBatch.objects.filter(
        user=user, expiration_date__isnull=False,
        expiration_date__gt=soon_30, expiration_date__lte=soon_60,
    ).select_related('ingredient', 'product').order_by('expiration_date')
    expiring_90 = InventoryBatch.objects.filter(
        user=user, expiration_date__isnull=False,
        expiration_date__gt=soon_60, expiration_date__lte=soon_90,
    ).select_related('ingredient', 'product').order_by('expiration_date')
    expired = InventoryBatch.objects.filter(
        user=user, expiration_date__isnull=False, expiration_date__lt=today,
    ).select_related('ingredient', 'product').order_by('-expiration_date')

    # Audit trail: recently changed orders
    audit_orders = ProductionOrder.objects.filter(user=user).select_related(
        'product', 'bom'
    ).order_by('-updated_at')[:25]

    return render(request, 'production/compliance.html', {
        'batches_no_quality': batches_no_quality,
        'orders_done_no_batch': orders_done_no_batch,
        'expiring_30': expiring_30,
        'expiring_60': expiring_60,
        'expiring_90': expiring_90,
        'expired': expired,
        'audit_orders': audit_orders,
        'today': today,
        'kpis': {
            'no_quality_count': batches_no_quality.count(),
            'no_batch_count': orders_done_no_batch.count(),
            'expiring_30_count': expiring_30.count(),
            'expiring_60_count': expiring_60.count(),
            'expiring_90_count': expiring_90.count(),
            'expired_count': expired.count(),
        },
    })


# ===== ORDER QUICK STATUS TRANSITIONS =====

@login_required
@require_POST
def order_quick_status(request, pk):
    """Transition an order's status via POST. Triggers traceability when DONE."""
    order = get_object_or_404(ProductionOrder, pk=pk, user=request.user)
    target = request.POST.get('status')
    if target not in {'IN_PROGRESS', 'DONE', 'CANCELLED', 'DRAFT'}:
        messages.error(request, "Estado inválido.")
        return redirect('production_order_list')

    if target == 'DONE' and not order.batches.exists():
        from traceability.services import ProductionService
        from django.core.exceptions import ValidationError
        try:
            ProductionService.register_production(
                product=order.product,
                bom=order.bom,
                quantity_produced=order.quantity_to_produce,
                internal_lot_code=f"LOT-{order.code}",
                user=request.user,
                notes=f"Generado automáticamente desde Orden {order.code}",
                production_date=order.end_date or timezone.localdate(),
                production_order=order,
            )
        except ValidationError as e:
            msg = getattr(e, 'message', str(e))
            messages.error(request, f"No se pudo finalizar la orden: {msg}")
            return redirect('production_order_list')
        except Exception as e:
            messages.error(request, f"Error al procesar producción: {e}")
            return redirect('production_order_list')

    order.status = target
    if target == 'IN_PROGRESS' and not order.start_date:
        order.start_date = timezone.localdate()
    if target == 'DONE' and not order.end_date:
        order.end_date = timezone.localdate()
    order.save(update_fields=['status', 'start_date', 'end_date', 'updated_at'])
    messages.success(request, f"Orden {order.code} actualizada a {order.get_status_display()}.")
    return redirect('production_order_list')


# ===== BOM DUPLICATE =====

@login_required
@require_POST
def bom_duplicate(request, pk):
    """Clone a BOM with all its lines. Adds _COPY suffix."""
    src = get_object_or_404(BillOfMaterial, pk=pk, user=request.user)
    with transaction.atomic():
        new_bom = BillOfMaterial.objects.create(
            user=request.user,
            name=f"{src.name} _COPY",
            code=(src.code or '') + "-COPY" if src.code else None,
            is_active=False,
            quantity=src.quantity,
        )
        # M2M
        new_bom.products.set(src.products.all())
        # Lines
        for line in src.lines.all():
            BomLine.objects.create(
                bom=new_bom,
                ingredient=line.ingredient,
                component_product=line.component_product,
                quantity=line.quantity,
                scrap_factor=line.scrap_factor or 0,
            )
    messages.success(request, f"Fórmula duplicada como '{new_bom.name}'.")
    return redirect('bom_update', pk=new_bom.pk)
