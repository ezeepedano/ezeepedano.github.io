from django.contrib import admin
from .models import DeliveryZone, Vehicle, DeliveryRoute, DeliveryStop

class DeliveryStopInline(admin.TabularInline):
    model = DeliveryStop
    extra = 1

@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ('date', 'vehicle', 'driver', 'status')
    list_filter = ('status', 'date')
    inlines = [DeliveryStopInline]

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('name', 'plate', 'driver', 'capacity_weight')

@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
