from django.contrib import admin
from .models import (
    WorkCenter, BillOfMaterial, BomLine, ProductionOrder,
    ProductSpecification, QualityResult, CompanyConfig,
    WorkInProcessStock,
)

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


class QualityResultInline(admin.TabularInline):
    model = QualityResult
    extra = 1

@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'parameter', 'specification', 'method', 'sort_order')
    list_filter = ('product',)
    search_fields = ('parameter', 'product__name')
    ordering = ('product', 'sort_order')

@admin.register(CompanyConfig)
class CompanyConfigAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'technical_director_name')
    fieldsets = (
        ('General', {
            'fields': ('company_name', 'logo_image', 'technical_director_name', 'signature_image'),
        }),
        ('Datos fiscales', {
            'fields': ('company_cuit', 'company_iva_condition', 'company_address'),
        }),
        ('Contacto', {
            'fields': ('company_phone', 'company_email', 'company_website', 'company_social'),
        }),
    )

    def has_add_permission(self, request):
        # Singleton: only allow one instance
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)


@admin.register(WorkInProcessStock)
class WorkInProcessStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'stage', 'quantity', 'unit', 'notes', 'updated_at')
    list_filter = ('stage', 'unit')
    search_fields = ('product__name', 'notes')
