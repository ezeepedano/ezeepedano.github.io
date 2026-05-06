from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from django.db.models import Q, Sum, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from .models import (
    IngredientLot,
    ProductionBatch,
    BatchConsumption,
    StockAlert,
    TraceabilityConfig
)
from .services import StockService, ProductionService, TraceabilityService
from inventory.models import Ingredient, Product
from production.models import BillOfMaterial, BomLine
from finance.models import Purchase, Provider, PurchaseCategory


class StockListView(LoginRequiredMixin, ListView):
    """Vista para consultar stock con alertas, KPIs, conexiones y sugerencias.

    Página production-ready con Soft UI:
    - KPIs (totales, valores, alertas)
    - Filtros por búsqueda, vista (bajo/próx vencer/vencidos/merma) y tipo
    - Filas enriquecidas (próximo lote a vencer, consumido 30d, valor, status)
    - Conexiones a compras, producción, kardex, FEFO
    - Auto-resolución de alertas obsoletas
    """
    template_name = 'traceability/stock_list.html'
    context_object_name = 'stock_data'

    def get_queryset(self):
        return None  # No usamos queryset, usamos context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        config = TraceabilityConfig.get_config()
        cutoff_30d = today - timedelta(days=30)
        expiry_threshold = today + timedelta(days=int(config.expiry_alert_days or 90))

        # 1) Mantenimiento de alertas: resolver primero las obsoletas, luego crear nuevas
        StockService.resolve_stale_alerts(user)
        StockService.check_and_create_alerts(user)

        # 2) Filtros
        q = (self.request.GET.get('q') or '').strip()
        view = (self.request.GET.get('view') or 'all').strip().lower()
        type_filter = (self.request.GET.get('type') or '').strip()

        # 3) Base queryset de ingredientes
        ingredients_qs = (
            Ingredient.objects
            .filter(user=user)
            .prefetch_related('lots')
        )
        if type_filter in ('raw_material', 'supply'):
            ingredients_qs = ingredients_qs.filter(type=type_filter)
        if q:
            ingredients_qs = ingredients_qs.filter(
                Q(name__icontains=q) | Q(code__icontains=q) |
                Q(lots__supplier_lot__icontains=q) |
                Q(lots__internal_id__icontains=q)
            ).distinct()

        # IDs de ingredientes que tienen al menos un BOM activo (para CTA "Crear orden")
        boms_ingredient_ids = set(
            BomLine.objects
            .filter(bom__user=user, bom__is_active=True, ingredient__isnull=False)
            .values_list('ingredient_id', flat=True)
        )

        # Consumo últimos 30 días por ingrediente
        consumed_30d_map = {
            row['ingredient_id']: row['total'] or Decimal('0')
            for row in (
                BatchConsumption.objects
                .filter(
                    production_batch__user=user,
                    production_batch__production_date__gte=cutoff_30d,
                    is_waste=False,
                )
                .values('ingredient_id')
                .annotate(total=Sum('quantity_consumed'))
            )
        }

        # 4) Construir filas enriquecidas
        ingredients_data = []
        total_stock_value = Decimal('0')
        low_stock_count = 0
        near_expiry_count_total = 0
        expired_count_total = 0
        wasted_count_total = 0

        for ing in ingredients_qs:
            active_lots = [l for l in ing.lots.all() if l.is_active]
            active_lots_sorted = sorted(
                active_lots,
                key=lambda l: (l.expiration_date or date.max, l.received_date or date.max)
            )
            lots_count = len(active_lots_sorted)
            total_stock = ing.stock_quantity or Decimal('0')

            cost = ing.cost_per_unit or Decimal('0')
            stock_value = (Decimal(str(total_stock)) * cost) if total_stock else Decimal('0')
            total_stock_value += stock_value

            # Per-lot value annotation (template can't multiply).
            for l in active_lots_sorted:
                qty = l.quantity_current or Decimal('0')
                l.value = qty * cost

            # FIFO head (oldest by received_date)
            oldest_lot = None
            if active_lots:
                oldest_lot = sorted(active_lots, key=lambda l: (l.received_date or date.max))[0]

            # Próximo a vencer
            next_to_expire = None
            for l in active_lots_sorted:
                if l.expiration_date:
                    next_to_expire = l
                    break

            # Conteos por ingrediente
            ing_near_expiry = sum(
                1 for l in active_lots
                if l.expiration_date and today <= l.expiration_date <= expiry_threshold
            )
            ing_expired = sum(
                1 for l in active_lots
                if l.expiration_date and l.expiration_date < today
            )
            ing_wasted = sum(1 for l in ing.lots.all() if l.is_wasted)

            near_expiry_count_total += ing_near_expiry
            expired_count_total += ing_expired
            wasted_count_total += ing_wasted

            # Estado del ingrediente
            threshold = config.low_stock_threshold_kg or Decimal('0')
            if total_stock <= 0:
                status = 'out'
            elif total_stock < threshold:
                status = 'low'
                low_stock_count += 1
            elif threshold > 0 and total_stock >= (threshold * Decimal('10')):
                status = 'overstocked'
            else:
                status = 'ok'

            consumed_30d = consumed_30d_map.get(ing.id, Decimal('0'))

            # Sugerencia de reabastecimiento (rule: 2x threshold - stock actual)
            suggested_qty = None
            if status in ('low', 'out') and threshold > 0:
                suggested_qty = (threshold * Decimal('2')) - Decimal(str(total_stock))
                if suggested_qty <= 0:
                    suggested_qty = threshold

            # Filtro de vista
            include_row = True
            if view == 'low' and status not in ('low', 'out'):
                include_row = False
            elif view == 'near_expiry' and ing_near_expiry == 0:
                include_row = False
            elif view == 'expired' and ing_expired == 0:
                include_row = False
            elif view == 'wasted' and ing_wasted == 0:
                include_row = False

            row = {
                'ingredient': ing,
                'total_stock': total_stock,
                'lots': active_lots_sorted,
                'lots_count': lots_count,
                'oldest_lot': oldest_lot,
                'next_to_expire': next_to_expire,
                'stock_value': stock_value,
                'status': status,
                'consumed_30d': consumed_30d,
                'usage_in_active_boms': 1 if ing.id in boms_ingredient_ids else 0,
                'has_bom': ing.id in boms_ingredient_ids,
                'near_expiry_count': ing_near_expiry,
                'expired_count': ing_expired,
                'wasted_count': ing_wasted,
                'suggested_qty': suggested_qty,
            }
            if include_row:
                ingredients_data.append(row)

        # 5) KPIs globales
        total_lots_active = IngredientLot.objects.filter(user=user, is_active=True).count()
        # Total ingredientes con stock > 0 (sobre el universo del usuario, sin filtros)
        total_ingredients = Ingredient.objects.filter(
            user=user, stock_quantity__gt=0
        ).count()

        # Lotes activos para batches
        batches_active = ProductionBatch.objects.filter(
            user=user, quantity_remaining__gt=0
        ).count()

        # Top 5 ingredientes consumidos en 30 días
        top_consumers_qs = (
            BatchConsumption.objects
            .filter(
                production_batch__user=user,
                production_batch__production_date__gte=cutoff_30d,
                is_waste=False,
            )
            .values('ingredient_id', 'ingredient__name', 'ingredient__unit')
            .annotate(total=Sum('quantity_consumed'))
            .order_by('-total')[:5]
        )
        top_consumers = [
            {
                'ingredient_id': r['ingredient_id'],
                'name': r['ingredient__name'],
                'unit': r['ingredient__unit'],
                'total': r['total'] or Decimal('0'),
            }
            for r in top_consumers_qs
        ]
        max_top = max((r['total'] for r in top_consumers), default=Decimal('1')) or Decimal('1')

        # Últimos 5 lotes producidos
        recent_batches = (
            ProductionBatch.objects
            .filter(user=user)
            .select_related('product')
            .order_by('-production_date', '-created_at')[:5]
        )

        # Compras pendientes de ingredientes (heurística por categoría con nombre 'ingrediente'/'materia prima')
        pending_ingredient_purchases = (
            Purchase.objects
            .filter(user=user, payment_status__in=['PENDING', 'PARTIAL'])
            .filter(
                Q(category__name__icontains='ingrediente') |
                Q(category__name__icontains='materia') |
                Q(category__name__icontains='insumo') |
                Q(description__icontains='Lote')
            )
            .select_related('provider', 'category')
            .order_by('due_date', '-date')[:6]
        )

        # Sugerencias de reabastecimiento (subset de ingredientes con suggested_qty)
        replenish_suggestions = [
            r for r in ingredients_data
            if r['suggested_qty'] and r['status'] in ('low', 'out')
        ][:8]

        # Alertas activas
        alerts = (
            StockAlert.objects
            .filter(
                Q(ingredient__user=user) | Q(ingredient_lot__user=user),
                is_resolved=False,
            )
            .select_related('ingredient', 'ingredient_lot', 'ingredient_lot__ingredient')
            .order_by('-created_at')
            .distinct()
        )

        context.update({
            # Filas + alertas
            'ingredients_data': ingredients_data,
            'alerts': alerts,
            'config': config,
            # KPIs
            'kpi_total_ingredients': total_ingredients,
            'kpi_total_lots_active': total_lots_active,
            'kpi_total_stock_value': total_stock_value,
            'kpi_low_stock_count': low_stock_count,
            'kpi_near_expiry_count': near_expiry_count_total,
            'kpi_expired_count': expired_count_total,
            'kpi_wasted_count': wasted_count_total,
            'kpi_batches_active': batches_active,
            # Filtros activos
            'search_query': q,
            'filter_view': view,
            'filter_type': type_filter,
            # Conexiones
            'top_consumers': top_consumers,
            'top_consumers_max': max_top,
            'recent_batches': recent_batches,
            'pending_ingredient_purchases': pending_ingredient_purchases,
            'replenish_suggestions': replenish_suggestions,
            'today': today,
            'expiry_threshold': expiry_threshold,
        })
        return context


class PurchaseListView(LoginRequiredMixin, ListView):
    """Unified Purchases hub.

    Single page to monitor every Purchase in the system: stock, assets-as-purchases
    (mirrored when the asset signal fires) and general expenses. Provides KPIs,
    multi-axis filtering (provider, status, search, date range) and inline
    actions (edit / delete / quick-pay).
    """
    model = Purchase
    template_name = 'traceability/purchase_list.html'
    context_object_name = 'purchases'
    paginate_by = 25

    def _base_qs(self):
        return Purchase.objects.filter(user=self.request.user).select_related(
            'provider', 'category'
        )

    def get_queryset(self):
        qs = self._base_qs()

        provider_id = self.request.GET.get('provider')
        if provider_id and provider_id.isdigit():
            qs = qs.filter(provider_id=int(provider_id))

        category_id = self.request.GET.get('category')
        if category_id and category_id.isdigit():
            qs = qs.filter(category_id=int(category_id))

        status = self.request.GET.get('status')
        if status == 'OVERDUE':
            qs = qs.filter(payment_status__in=['PENDING', 'PARTIAL'], due_date__lt=date.today())
        elif status in ('PENDING', 'PARTIAL', 'PAID'):
            qs = qs.filter(payment_status=status)

        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        search = (self.request.GET.get('q') or '').strip()
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(description__icontains=search)
                | Q(provider__name__icontains=search)
                | Q(category__name__icontains=search)
            )

        return qs.order_by('-date', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = self._base_qs()
        today = date.today()
        month_start = today.replace(day=1)

        # KPIs are computed on the unfiltered scope so users always see their
        # full financial picture, regardless of which filter they applied.
        agg = base.aggregate(
            total_amount=Sum('amount'),
            total_paid=Sum('paid_amount'),
            total_count=Count('id'),
        )
        total_amount = agg['total_amount'] or 0
        total_paid = agg['total_paid'] or 0
        total_balance = total_amount - total_paid

        pending_qs = base.filter(payment_status__in=['PENDING', 'PARTIAL'])
        pending_count = pending_qs.count()
        pending_amount = pending_qs.aggregate(s=Sum(F('amount') - F('paid_amount')))['s'] or 0

        overdue_qs = pending_qs.filter(due_date__lt=today)
        overdue_count = overdue_qs.count()
        overdue_amount = overdue_qs.aggregate(s=Sum(F('amount') - F('paid_amount')))['s'] or 0

        month_qs = base.filter(date__gte=month_start)
        month_count = month_qs.count()
        month_amount = month_qs.aggregate(s=Sum('amount'))['s'] or 0

        context.update({
            'providers': Provider.objects.filter(user=self.request.user).order_by('name'),
            'categories': PurchaseCategory.objects.filter(user=self.request.user).order_by('name'),
            'kpi_total_count': agg['total_count'] or 0,
            'kpi_total_amount': total_amount,
            'kpi_total_balance': total_balance,
            'kpi_pending_count': pending_count,
            'kpi_pending_amount': pending_amount,
            'kpi_overdue_count': overdue_count,
            'kpi_overdue_amount': overdue_amount,
            'kpi_month_count': month_count,
            'kpi_month_amount': month_amount,
            'filter_provider': self.request.GET.get('provider', ''),
            'filter_category': self.request.GET.get('category', ''),
            'filter_status': self.request.GET.get('status', ''),
            'filter_date_from': self.request.GET.get('date_from', ''),
            'filter_date_to': self.request.GET.get('date_to', ''),
            'search_query': self.request.GET.get('q', ''),
            'today': today,
        })
        return context


class PurchaseCreateView(LoginRequiredMixin, CreateView):
    """Vista para registrar compra/ingreso de stock."""
    model = IngredientLot
    template_name = 'traceability/purchase_form.html'
    fields = ['ingredient', 'quantity_initial', 'supplier_lot', 'expiration_date']
    success_url = reverse_lazy('traceability:stock_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ingredients'] = Ingredient.objects.filter(user=self.request.user)
        context['providers'] = Provider.objects.filter(user=self.request.user)
        context['categories'] = PurchaseCategory.objects.filter(user=self.request.user)
        
        # Pre-generar ID para el ingrediente seleccionado si viene en GET
        ingredient_id = self.request.GET.get('ingredient')
        if ingredient_id:
            try:
                ingredient = Ingredient.objects.get(pk=ingredient_id, user=self.request.user)
                context['suggested_id'] = StockService.get_next_internal_id(ingredient)
            except Ingredient.DoesNotExist:
                pass
        
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['ingredient'].queryset = Ingredient.objects.filter(user=self.request.user)
        return form

    def get_initial(self):
        initial = super().get_initial()
        ingredient_id = self.request.GET.get('ingredient')
        if ingredient_id and ingredient_id.isdigit():
            try:
                ing = Ingredient.objects.get(pk=int(ingredient_id), user=self.request.user)
                initial['ingredient'] = ing
            except Ingredient.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        try:
            ingredient = form.cleaned_data['ingredient']
            quantity = form.cleaned_data['quantity_initial']
            supplier_lot = form.cleaned_data['supplier_lot']
            expiration_date = form.cleaned_data['expiration_date']
            
            # Extract NON-FORM fields for Finance
            cost_per_kg = self.request.POST.get('cost_per_kg')
            provider_id = self.request.POST.get('provider')
            category_id = self.request.POST.get('category')
            payment_status = self.request.POST.get('payment_status', 'PENDING')
            
            provider = None
            if provider_id:
                provider = Provider.objects.get(pk=provider_id, user=self.request.user)
                
            category = None
            if category_id:
                category = PurchaseCategory.objects.get(pk=category_id, user=self.request.user)
            
            # Usar servicio para crear el lote AND Finance Record
            lot = StockService.register_purchase(
                ingredient=ingredient,
                quantity=quantity,
                supplier_lot=supplier_lot,
                received_date=timezone.now().date(),
                expiration_date=expiration_date,
                user=self.request.user,
                # New logic
                cost_per_kg=float(cost_per_kg) if cost_per_kg else 0.0,
                provider=provider,
                category=category,
                payment_status=payment_status
            )
            
            messages.success(
                self.request,
                f'✓ Compra registrada: {lot.internal_id} - {quantity} kg de {ingredient.name}'
            )
            
            return redirect(self.success_url)
            
        except Exception as e:
            messages.error(self.request, f'Error al registrar compra: {str(e)}')
            return self.form_invalid(form)


class ProductionCreateView(LoginRequiredMixin, CreateView):
    """Vista para registrar producción con trazabilidad."""
    model = ProductionBatch
    template_name = 'traceability/production_form.html'
    fields = ['product', 'bom', 'quantity_produced', 'internal_lot_code', 'notes']
    success_url = reverse_lazy('traceability:production_history')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(user=self.request.user)
        context['boms'] = BillOfMaterial.objects.filter(is_active=True, user=self.request.user)
        
        # Si viene un producto en GET, obtener sus BOMs
        product_id = self.request.GET.get('product')
        if product_id:
            try:
                product = Product.objects.get(pk=product_id, user=self.request.user)
                context['selected_product'] = product
                context['product_boms'] = product.boms.filter(is_active=True)
            except Product.DoesNotExist:
                pass
        
        return context
    
    def form_valid(self, form):
        try:
            product = form.cleaned_data['product']
            bom = form.cleaned_data.get('bom')
            quantity_produced = form.cleaned_data['quantity_produced']
            internal_lot_code = form.cleaned_data['internal_lot_code']
            notes = form.cleaned_data.get('notes')
            
            # Verificar que el lote no exista — scope per-user to avoid
            # leaking that another tenant uses the same code.
            if ProductionBatch.objects.filter(
                user=self.request.user,
                internal_lot_code=internal_lot_code,
            ).exists():
                messages.error(
                    self.request,
                    f'El código de lote {internal_lot_code} ya existe. Use uno diferente.'
                )
                return self.form_invalid(form)
            
            # Si no hay BOM, buscar una activa para el producto
            if not bom:
                bom = product.boms.filter(is_active=True).first()
                if not bom:
                    messages.error(
                        self.request,
                        f'No hay receta (BOM) configurada para {product.name}'
                    )
                    return self.form_invalid(form)
            
            # Registrar producción con el servicio
            batch = ProductionService.register_production(
                product=product,
                bom=bom,
                quantity_produced=quantity_produced,
                internal_lot_code=internal_lot_code,
                user=self.request.user,
                notes=notes
            )
            
            messages.success(
                self.request,
                f'✓ Producción registrada: {batch.internal_lot_code} - {quantity_produced} kg de {product.name}'
            )
            
            return redirect('traceability:production_detail', pk=batch.pk)
            
        except Exception as e:
            messages.error(self.request, f'Error al registrar producción: {str(e)}')
            return self.form_invalid(form)


class ProductionHistoryView(LoginRequiredMixin, ListView):
    """Vista para ver historial de producciones."""
    model = ProductionBatch
    template_name = 'traceability/production_history.html'
    context_object_name = 'batches'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ProductionBatch.objects.filter(user=self.request.user).select_related(
            'product', 'bom', 'user'
        ).prefetch_related('consumptions')
        
        # Filtros opcionales
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(user=self.request.user)
        context['status_choices'] = ProductionBatch.STATUS_CHOICES
        
        # Estadísticas generales
        total_batches = ProductionBatch.objects.filter(status='COMPLETED', user=self.request.user).count()
        context['total_batches'] = total_batches
        
        return context


class ProductionDetailView(LoginRequiredMixin, DetailView):
    """Vista de detalle de un lote de producción con trazabilidad completa."""
    model = ProductionBatch
    template_name = 'traceability/production_detail.html'
    context_object_name = 'batch'

    def get_queryset(self):
        return ProductionBatch.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtener trazabilidad completa
        traceability = TraceabilityService.get_batch_traceability(self.object)
        context['traceability'] = traceability

        return context


class AlertListView(LoginRequiredMixin, ListView):
    """Vista para listar alertas de stock."""
    model = StockAlert
    template_name = 'traceability/alert_list.html'
    context_object_name = 'alerts'
    paginate_by = 50
    
    def get_queryset(self):
        # Actualizar alertas
        StockService.check_and_create_alerts(self.request.user)
        
        queryset = StockAlert.objects.filter(
            Q(ingredient__user=self.request.user) | Q(ingredient_lot__user=self.request.user)
        ).select_related(
            'ingredient', 'ingredient_lot'
        )
        
        # Mostrar solo activas por defecto
        show_resolved = self.request.GET.get('show_resolved')
        if not show_resolved:
            queryset = queryset.filter(is_resolved=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Contar por tipo
        context['low_stock_count'] = StockAlert.objects.filter(
            ingredient__user=self.request.user,
            alert_type='LOW_STOCK', is_resolved=False
        ).count()
        context['near_expiry_count'] = StockAlert.objects.filter(
            ingredient_lot__user=self.request.user,
            alert_type='NEAR_EXPIRY', is_resolved=False
        ).count()
        context['expired_count'] = StockAlert.objects.filter(
            ingredient_lot__user=self.request.user,
            alert_type='EXPIRED', is_resolved=False
        ).count()
        
        return context
