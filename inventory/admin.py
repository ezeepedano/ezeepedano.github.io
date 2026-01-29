from django.contrib import admin
from .models import Category, Product, Ingredient, Recipe, ProductionOrder, Batch, SupplierPrice

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'category', 'sale_price', 'stock_quantity')
    search_fields = ('sku', 'name')
    list_filter = ('category',)

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'stock_quantity', 'cost_per_unit')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('number', 'product', 'ingredient', 'quantity', 'expiration_date')
    list_filter = ('expiration_date',)
    search_fields = ('number', 'product__name')

@admin.register(SupplierPrice)
class SupplierPriceAdmin(admin.ModelAdmin):
    list_display = ('provider', 'product', 'ingredient', 'price')
    list_filter = ('provider',)

# Legacy Models
admin.site.register(Recipe)
admin.site.register(ProductionOrder)
