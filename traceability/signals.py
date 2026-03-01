"""
Señales de Django para automatizar la trazabilidad.
Auto-asigna lotes de producción cuando se confirma una venta.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from sales.models import Sale
from .services import SalesTraceabilityService
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Sale)
def auto_allocate_production_batches(sender, instance, created, **kwargs):
    """
    Asigna automáticamente lotes de producción cuando una venta se confirma.
    
    Condiciones de activación:
    - Estado de venta cambia a estados confirmados
    - Existen items en la venta
    """
    # Estados que activan la asignación (personalizar según workflow)
    ALLOCATION_STATUSES = ['Pagado', 'Confirmado', 'Listo para enviar', 'Entregado']
    
    if instance.status in ALLOCATION_STATUSES:
        # Verificar si ya tiene asignaciones
        has_allocations = False
        if instance.items.exists():
            has_allocations = any(
                item.batch_allocations.exists() for item in instance.items.all()
            )
        
        if not has_allocations:
            try:
                result = SalesTraceabilityService.auto_allocate_sale(instance)
                logger.info(
                    f"✓ Auto-asignación exitosa para venta {instance.order_id}: "
                    f"{result['total_allocated']} lotes asignados"
                )
            except ValidationError as e:
                logger.error(
                    f"✗ Falló auto-asignación para venta {instance.order_id}: {e}"
                )
                # No levantar excepción para evitar bloquear creación de venta
            except Exception as e:
                logger.error(
                    f"✗ Error inesperado en auto-asignación para venta {instance.order_id}: {e}"
                )


@receiver(post_save, sender='traceability.ProductionBatch')
def log_batch_completion(sender, instance, **kwargs):
    """
    Registra cuando un lote de producción se completa y queda disponible para asignación.
    """
    if instance.status == 'COMPLETED' and not instance.is_allocated:
        logger.info(
            f"✓ Lote de producción {instance.internal_lot_code} completado. "
            f"{instance.quantity_remaining} kg disponibles para asignación."
        )


from inventory.models import Ingredient
from .models import IngredientLot
from django.db.models import Sum
from decimal import Decimal
from django.db.models.signals import post_delete

@receiver(post_save, sender=Ingredient)
def sync_ingredient_stock_to_lots(sender, instance, **kwargs):
    """
    Direction A: Manual Edit.
    If Ingredient.stock_quantity is changed manually (e.g. via Django Admin or Form),
    we must ensure the Lots sum up to this new value.
    """
    # Avoid recursion if this save was triggered by the other signal
    if getattr(instance, '_syncing_from_lots', False):
        return

    total_lots = IngredientLot.objects.filter(
        ingredient=instance, 
        is_active=True
    ).aggregate(total=Sum('quantity_current'))['total'] or Decimal('0')

    diff = instance.stock_quantity - total_lots
    
    # Tolerancia para flotantes
    if abs(diff) < Decimal('0.001'):
        return

    # If diff > 0: We have "phantom" stock. Create an adjustment lot.
    if diff > 0:
        from datetime import date
        count = IngredientLot.objects.filter(ingredient=instance).count() + 1
        internal_id = f"ADJ-{instance.id}-{date.today().strftime('%Y%m%d')}-{count}"
        
        IngredientLot.objects.create(
            user=instance.user,
            ingredient=instance,
            internal_id=internal_id,
            quantity_initial=diff,
            quantity_current=diff,
            supplier_lot="AJUSTE-MANUAL",
            received_date=date.today(),
            is_active=True
        )
    
    # If diff < 0: We have less physical stock than lots. Consume from lots (FIFO) to shrink.
    else:
        to_remove = abs(diff)
        lots = IngredientLot.objects.filter(
            ingredient=instance, 
            is_active=True
        ).order_by('received_date', 'created_at')
        
        for lot in lots:
            if to_remove <= 0:
                break
            
            consume_amount = min(lot.quantity_current, to_remove)
            
            # We consume without triggering the OTHER signal loop? 
            # The other signal listens to IngredientLot.save
            # We can't easily suppress that signal from here without disabling it globally.
            # But the other signal uses .update() on Ingredient, which DOES NOT trigger this signal.
            # So it is safe!
            
            lot.quantity_current -= consume_amount
            if lot.quantity_current <= 0:
                lot.is_active = False
            lot.save()
            
            to_remove -= consume_amount


@receiver(post_save, sender=IngredientLot)
@receiver(post_delete, sender=IngredientLot)
def sync_lots_to_ingredient_stock(sender, instance, **kwargs):
    """
    Direction B: System Consumption / Lot Update.
    If a Lot changes (consumed, created, deleted), update the Ingredient total.
    We use .update() to avoid triggering Signal A.
    """
    ingredient = instance.ingredient
    
    total_lots = IngredientLot.objects.filter(
        ingredient=ingredient, 
        is_active=True
    ).aggregate(total=Sum('quantity_current'))['total'] or Decimal('0')
    
    # Use .update to bypass Ingredient.save signals (prevents loop)
    Ingredient.objects.filter(pk=ingredient.pk).update(stock_quantity=total_lots)


# ===== NEW AUTOMATIONS =====

from .models import ProductionBatch
from finance.models import Purchase
from datetime import date, timedelta

@receiver(pre_save, sender=ProductionBatch)
def auto_generate_batch_number(sender, instance, **kwargs):
    """Auto-generate batch number if empty: SKU-YYYYMMDD-SEQ"""
    if not instance.internal_lot_code and instance.product:
        today_str = date.today().strftime('%Y%m%d')
        sku = instance.product.sku[:6].upper() if instance.product.sku else "PROD"
        
        # Count batches created today for this product
        today_count = ProductionBatch.objects.filter(
            product=instance.product,
            created_at__date=date.today()
        ).count() + 1
        
        instance.internal_lot_code = f"{sku}-{today_str}-{today_count:03d}"
        logger.info(f"✓ Auto-generated batch code: {instance.internal_lot_code}")


@receiver(post_save, sender=IngredientLot)
def check_expiry_alert(sender, instance, created, **kwargs):
    """Alert if ingredient lot is expiring soon (within 30 days)"""
    if instance.is_active and instance.expiration_date:
        days_until_expiry = (instance.expiration_date - date.today()).days
        
        if 0 < days_until_expiry <= 30:
            logger.warning(
                f"⚠️ EXPIRY ALERT: {instance.ingredient.name} (Lot: {instance.internal_id}) "
                f"expires in {days_until_expiry} days ({instance.expiration_date})"
            )
        elif days_until_expiry <= 0:
            logger.error(
                f"❌ EXPIRED: {instance.ingredient.name} (Lot: {instance.internal_id}) "
                f"expired on {instance.expiry_date}"
            )


@receiver(post_save, sender=ProductionBatch)
def detect_production_waste(sender, instance, **kwargs):
    """Detect waste if remaining quantity is suspiciously low"""
    if instance.quantity_remaining is not None and instance.quantity_initial:
        waste_percent = ((instance.quantity_initial - instance.quantity_remaining) / instance.quantity_initial) * 100
        
        WASTE_THRESHOLD = 15  # Alert if more than 15% waste
        
        if waste_percent > WASTE_THRESHOLD and not instance.is_allocated:
            logger.warning(
                f"⚠️ WASTE DETECTED: Batch {instance.internal_lot_code} has {waste_percent:.1f}% waste "
                f"({instance.quantity_initial - instance.quantity_remaining} kg lost)"
            )


@receiver(post_save, sender=Purchase)
def auto_suggest_lot_creation(sender, instance, created, **kwargs):
    """Log suggestion to create ingredient lots when purchase is created"""
    if created:
        logger.info(
            f"💡 SUGGESTION: Purchase #{instance.id} created. "
            f"Consider creating IngredientLots for traceability."
        )
