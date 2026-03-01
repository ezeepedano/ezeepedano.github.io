from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Product, Ingredient
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ===== PHASE 7: INVENTORY ADVANCED AUTOMATIONS =====

@receiver(post_save, sender=Ingredient)
def check_low_stock_alert(sender, instance, **kwargs):
    """Create alert when ingredient stock is low."""
    LOW_STOCK_THRESHOLD = 10  # kg or units
    
    if instance.stock_quantity < LOW_STOCK_THRESHOLD:
        logger.warning(
            f"⚠️ LOW STOCK ALERT: {instance.name} has only {instance.stock_quantity} {instance.unit} remaining (<{LOW_STOCK_THRESHOLD})"
        )


@receiver(post_save, sender=Product)
def check_product_low_stock(sender, instance, **kwargs):
    """Alert when product stock is low."""
    LOW_STOCK_THRESHOLD = 5  # units
    
    if instance.stock_quantity < LOW_STOCK_THRESHOLD:
        logger.warning(
            f"⚠️ LOW STOCK ALERT: Product '{instance.name}' has only {instance.stock_quantity} units remaining (<{LOW_STOCK_THRESHOLD})"
        )


@receiver(pre_save, sender=Ingredient)
def set_unit_defaults_by_type(sender, instance, **kwargs):
    """Auto-set unit based on ingredient type if not specified."""
    if not instance.unit or instance.unit == '':
        if instance.type == 'raw_material':
            instance.unit = 'kg'  # Raw materials default to kg
        elif instance.type == 'supply':
            instance.unit = 'u'  # Supplies default to units


# ===== PHASE 7 CONTINUED: INVENTORY ADVANCED =====

from production.models import BillOfMaterial

@receiver(post_save, sender='production.BillOfMaterial')
def auto_calculate_product_weight(sender, instance, **kwargs):
    """Auto-calculate product weight from BOM composition."""
    if instance.products.exists():
        product = instance.products.first()
        
        # Calculate total weight from raw material ingredients
        total_weight = Decimal('0')
        for line in instance.lines.all():
            if line.ingredient and line.ingredient.type == 'raw_material':
                # Convert percentage to kg
                percentage = line.quantity
                kg = (percentage / 100) * instance.quantity
                total_weight += kg
        
        if total_weight > 0 and product.weight_kg != total_weight:
            product.weight_kg = total_weight
            product.save(update_fields=['weight_kg'])
            logger.info(
                f"✓ Auto-calculated weight for {product.name}: {total_weight} kg (from BOM)"
            )


@receiver(pre_save, sender=Product)
def set_unit_measure_by_category(sender, instance, **kwargs):
    """Auto-set unit measure based on product category."""
    if not instance.pk and instance.category:
        category_name = instance.category.name.lower()
        
        if 'suplemento' in category_name or 'producto terminado' in category_name:
            instance.unit_measure = 'u'  # Units
        elif 'ingrediente' in category_name or 'materia prima' in category_name:
            instance.unit_measure = 'kg'  # Kilograms
        elif 'bebida' in category_name or 'líquido' in category_name:
            instance.unit_measure = 'l'  # Liters


# ===== PHASE 7 FINAL: SUPPLIER PRICE LOOKUP =====

@receiver(pre_save, sender=Ingredient)
def lookup_supplier_price(sender, instance, **kwargs):
    """Auto-lookup last price from supplier for this ingredient."""
    if instance.pk:  # Only on updates
        from inventory.models import SupplierPrice
        
        # Find most recent supplier price for this ingredient
        latest_price = SupplierPrice.objects.filter(
            ingredient=instance
        ).order_by('-last_updated').first()
        
        if latest_price and latest_price.price != instance.cost_per_unit:
            logger.info(
                f"💡 PRICE SUGGESTION: Ingredient '{instance.name}' - "
                f"Current: ${instance.cost_per_unit}, Latest supplier price: ${latest_price.price} "
                f"from {latest_price.provider.name}"
            )
