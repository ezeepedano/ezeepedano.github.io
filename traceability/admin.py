from django.contrib import admin
from .models import (
    IngredientLot,
    ProductionBatch,
    BatchConsumption,
    StockAlert,
    TraceabilityConfig
)


@admin.register(IngredientLot)
class IngredientLotAdmin(admin.ModelAdmin):
    list_display = [
        'internal_id', 
        'ingredient', 
        'quantity_current', 
        'quantity_initial',
        'supplier_lot',
        'expiration_date',
        'is_active',
        'is_wasted'
    ]
    list_filter = ['is_active', 'is_wasted', 'ingredient', 'expiration_date']
    search_fields = ['internal_id', 'supplier_lot', 'ingredient__name']
    readonly_fields = ['created_at', 'updated_at', 'received_date']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('internal_id', 'ingredient', 'user')
        }),
        ('Cantidades', {
            'fields': ('quantity_initial', 'quantity_current')
        }),
        ('Trazabilidad', {
            'fields': ('supplier_lot', 'expiration_date', 'received_date')
        }),
        ('Estado', {
            'fields': ('is_active', 'is_wasted')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display = [
        'internal_lot_code',
        'product',
        'quantity_produced',
        'production_date',
        'status'
    ]
    list_filter = ['status', 'product', 'production_date']
    search_fields = ['internal_lot_code', 'product__name', 'product__sku']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('internal_lot_code', 'user')
        }),
        ('Producción', {
            'fields': ('product', 'bom', 'production_order', 'quantity_produced')
        }),
        ('Fechas', {
            'fields': ('production_date',)
        }),
        ('Estado', {
            'fields': ('status', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class BatchConsumptionInline(admin.TabularInline):
    model = BatchConsumption
    extra = 0
    readonly_fields = ['created_at']
    fields = ['ingredient', 'ingredient_lot', 'quantity_consumed', 'is_waste', 'created_at']


@admin.register(BatchConsumption)
class BatchConsumptionAdmin(admin.ModelAdmin):
    list_display = [
        'production_batch',
        'ingredient',
        'ingredient_lot',
        'quantity_consumed',
        'is_waste'
    ]
    list_filter = ['is_waste', 'ingredient', 'production_batch__status']
    search_fields = [
        'production_batch__internal_lot_code',
        'ingredient__name',
        'ingredient_lot__internal_id'
    ]
    readonly_fields = ['created_at']


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = [
        'alert_type',
        'ingredient',
        'ingredient_lot',
        'is_resolved',
        'created_at'
    ]
    list_filter = ['alert_type', 'is_resolved', 'created_at']
    search_fields = ['message', 'ingredient__name', 'ingredient_lot__internal_id']
    readonly_fields = ['created_at', 'resolved_at']
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_resolved=True, resolved_at=timezone.now())
    mark_as_resolved.short_description = "Marcar como resueltas"


@admin.register(TraceabilityConfig)
class TraceabilityConfigAdmin(admin.ModelAdmin):
    list_display = [
        'waste_threshold_kg',
        'low_stock_threshold_kg',
        'expiry_alert_days',
        'updated_at'
    ]
    readonly_fields = ['updated_at']
    
    def has_add_permission(self, request):
        # Solo permitir una configuración
        return not TraceabilityConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar la configuración
        return False
