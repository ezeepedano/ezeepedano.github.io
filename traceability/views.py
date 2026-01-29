from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from decimal import Decimal

from .models import (
    IngredientLot,
    ProductionBatch,
    StockAlert,
    TraceabilityConfig
)
from .services import StockService, ProductionService, TraceabilityService
from inventory.models import Ingredient, Product
from production.models import BillOfMaterial


class StockListView(LoginRequiredMixin, ListView):
    """Vista para consultar stock con alertas."""
    template_name = 'traceability/stock_list.html'
    context_object_name = 'stock_data'
    
    def get_queryset(self):
        return None  # No usamos queryset, usamos context
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actualizar alertas
        StockService.check_and_create_alerts()
        
        # Obtener resumen de stock
        stock_summary = StockService.get_stock_summary()
        context['ingredients_data'] = stock_summary['ingredients']
        context['alerts'] = stock_summary['alerts']
        context['config'] = TraceabilityConfig.get_config()
        
        return context


class PurchaseCreateView(LoginRequiredMixin, CreateView):
    """Vista para registrar compra/ingreso de stock."""
    model = IngredientLot
    template_name = 'traceability/purchase_form.html'
    fields = ['ingredient', 'quantity_initial', 'supplier_lot', 'expiration_date']
    success_url = reverse_lazy('traceability:stock_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ingredients'] = Ingredient.objects.all()
        
        # Pre-generar ID para el ingrediente seleccionado si viene en GET
        ingredient_id = self.request.GET.get('ingredient')
        if ingredient_id:
            try:
                ingredient = Ingredient.objects.get(pk=ingredient_id)
                context['suggested_id'] = StockService.get_next_internal_id(ingredient)
            except Ingredient.DoesNotExist:
                pass
        
        return context
    
    def form_valid(self, form):
        try:
            ingredient = form.cleaned_data['ingredient']
            quantity = form.cleaned_data['quantity_initial']
            supplier_lot = form.cleaned_data['supplier_lot']
            expiration_date = form.cleaned_data['expiration_date']
            
            # Usar servicio para crear el lote
            lot = StockService.register_purchase(
                ingredient=ingredient,
                quantity=quantity,
                supplier_lot=supplier_lot,
                expiration_date=expiration_date,
                user=self.request.user
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
        context['products'] = Product.objects.all()
        context['boms'] = BillOfMaterial.objects.filter(is_active=True)
        
        # Si viene un producto en GET, obtener sus BOMs
        product_id = self.request.GET.get('product')
        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
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
            
            # Verificar que el lote no exista
            if ProductionBatch.objects.filter(internal_lot_code=internal_lot_code).exists():
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
        queryset = ProductionBatch.objects.select_related(
            'product', 'bom', 'user'
        ).prefetch_related('consumptions').all()
        
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
        context['products'] = Product.objects.all()
        context['status_choices'] = ProductionBatch.STATUS_CHOICES
        
        # Estadísticas generales
        total_batches = ProductionBatch.objects.filter(status='COMPLETED').count()
        context['total_batches'] = total_batches
        
        return context


class ProductionDetailView(LoginRequiredMixin, DetailView):
    """Vista de detalle de un lote de producción con trazabilidad completa."""
    model = ProductionBatch
    template_name = 'traceability/production_detail.html'
    context_object_name = 'batch'
    
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
        StockService.check_and_create_alerts()
        
        queryset = StockAlert.objects.select_related(
            'ingredient', 'ingredient_lot'
        ).all()
        
        # Mostrar solo activas por defecto
        show_resolved = self.request.GET.get('show_resolved')
        if not show_resolved:
            queryset = queryset.filter(is_resolved=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Contar por tipo
        context['low_stock_count'] = StockAlert.objects.filter(
            alert_type='LOW_STOCK', is_resolved=False
        ).count()
        context['near_expiry_count'] = StockAlert.objects.filter(
            alert_type='NEAR_EXPIRY', is_resolved=False
        ).count()
        context['expired_count'] = StockAlert.objects.filter(
            alert_type='EXPIRED', is_resolved=False
        ).count()
        
        return context
