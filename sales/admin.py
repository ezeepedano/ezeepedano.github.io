"""
Sales Admin Configuration

Registers Sales models in Django admin for debugging and data management.
"""

from django.contrib import admin
from .models import Sale, SaleItem, Customer, CustomerStats


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('product', 'product_title', 'sku', 'quantity', 'unit_price')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'order_id', 'date', 'channel', 'customer', 'total',
        'payment_status', 'status', 'stock_deducted',
    )
    list_filter = ('channel', 'payment_status', 'status', 'stock_deducted')
    search_fields = ('order_id', 'customer__name', 'recipient_name')
    date_hierarchy = 'date'
    inlines = [SaleItemInline]
    raw_id_fields = ('customer',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'city', 'state', 'created_at')
    list_filter = ('state', 'country')
    search_fields = ('name', 'email', 'document_number', 'billing_name')
    readonly_fields = ('dedup_key', 'created_at', 'updated_at')
    list_per_page = 50


@admin.register(CustomerStats)
class CustomerStatsAdmin(admin.ModelAdmin):
    list_display = (
        'customer', 'total_orders', 'total_spent', 'avg_ticket',
        'segment', 'days_since_last_order',
    )
    list_filter = ('segment',)
    search_fields = ('customer__name',)
    readonly_fields = ('updated_at',)
    list_per_page = 50
