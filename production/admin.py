from django.contrib import admin
from .models import WorkCenter, BillOfMaterial, BomLine, ProductionOrder

class BomLineInline(admin.TabularInline):
    model = BomLine
    extra = 1

@admin.register(BillOfMaterial)
class BillOfMaterialAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'code', 'quantity', 'is_active')
    search_fields = ('product__name', 'name', 'code')
    inlines = [BomLineInline]

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('code', 'product', 'quantity_to_produce', 'status', 'start_date', 'origin')
    list_filter = ('status', 'start_date')
    search_fields = ('code', 'product__name', 'origin')

@admin.register(WorkCenter)
class WorkCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'hourly_cost')
