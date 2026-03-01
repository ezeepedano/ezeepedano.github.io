from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DeliveryRoute
from sales.models import Sale
import logging

logger = logging.getLogger(__name__)

# ===== PHASE 9: LOGISTICS ADVANCED AUTOMATIONS =====

@receiver(post_save, sender=DeliveryRoute)
def update_sale_status_on_route_completion(sender, instance, **kwargs):
    """Auto-update Sale status when delivery route is completed."""
    if instance.status == 'COMPLETADO':
        # Get all sales in this route
        sales = instance.sales.all()
        
        for sale in sales:
            if sale.status != 'Entregado':
                old_status = sale.status
                sale.status = 'Entregado'
                sale.save(update_fields=['status'])
                
                logger.info(
                    f"✓ Sale #{sale.order_id} status updated: {old_status} → Entregado (Route completed)"
                )


# ===== PHASE 10: CROSS-MODULE ADVANCED AUTOMATIONS =====

from inventory.models import Ingredient

@receiver(post_save, sender=Ingredient)
def suggest_purchase_on_low_stock(sender, instance, **kwargs):
    """Suggest creating purchase order when ingredient stock is critically low."""
    CRITICAL_THRESHOLD = 5  # kg or units
    
    if instance.stock_quantity < CRITICAL_THRESHOLD:
        logger.warning(
            f"💡 PURCHASE SUGGESTION: {instance.name} stock is critically low ({instance.stock_quantity} {instance.unit}). "
            f"Consider creating a purchase order."
        )


# ===== PHASE 9 CONTINUED: LOGISTICS ADVANCED =====

from sales.models import Sale

@receiver(post_save, sender=Sale)
def auto_detect_zone_from_sale(sender, instance, created, **kwargs):
    """Auto-detect delivery zone from sale address."""
    if created and instance.city:
        from logistics.models import DeliveryZone
        
        # Find matching zone by city
        matching_zones = DeliveryZone.objects.filter(
            name__icontains=instance.city
        )
        
        if matching_zones.exists():
            zone = matching_zones.first()
            logger.info(
                f"💡 ZONE DETECTED: Sale #{instance.order_id} → Zone '{zone.name}' (auto-detected from city: {instance.city})"
            )


@receiver(post_save, sender=DeliveryRoute)
def auto_assign_driver_by_zone(sender, instance, created, **kwargs):
    """Auto-suggest driver assignment based on zone and availability."""
    if created and instance.zone:
        from logistics.models import Driver
        
        # Find available drivers for this zone
        # This would require a 'preferred_zones' field on Driver model
        # For now, just log suggestion
        available_drivers = Driver.objects.filter(is_active=True)
        
        if available_drivers.exists():
            driver = available_drivers.first()
            logger.info(
                f"💡 DRIVER SUGGESTION: Route for zone '{instance.zone.name}' → Consider assigning: {driver.name}"
            )


# ===== PHASE 9 FINAL: ROUTE OPTIMIZATION & AUTO-ASSIGNMENT =====

@receiver(post_save, sender=Sale)
def suggest_route_assignment_for_sale(sender, instance, created, **kwargs):
    """Auto-suggest assigning sale to existing delivery route."""
    if created and instance.city:
        from logistics.models import DeliveryRoute, DeliveryZone
        
        # Find zone for this sale
        matching_zones = DeliveryZone.objects.filter(name__icontains=instance.city)
        
        if matching_zones.exists():
            zone = matching_zones.first()
            
            # Find active routes for this zone with available capacity
            active_routes = DeliveryRoute.objects.filter(
                zone=zone,
                status__in=['PENDING', 'IN_PROGRESS']
            )
            
            if active_routes.exists():
                route = active_routes.first()
                logger.info(
                    f"💡 ROUTE ASSIGNMENT: Sale #{instance.order_id} → "
                    f"Suggest adding to Route '{route.code}' (Zone: {zone.name})"
                )


@receiver(post_save, sender=DeliveryRoute)
def suggest_route_optimization(sender, instance, created, **kwargs):
    """Suggest TSP-based route optimization for delivery efficiency."""
    if created or instance.status == 'PENDING':
        # Count stops in route
        sales_count = instance.sales.count() if hasattr(instance, 'sales') else 0
        
        if sales_count > 3:
            logger.info(
                f"💡 ROUTE OPTIMIZATION: Route '{instance.code}' has {sales_count} stops. "
                f"Consider applying TSP (Traveling Salesman Problem) algorithm for optimal sequencing. "
                f"Use Google Maps Directions API for real distances."
            )
