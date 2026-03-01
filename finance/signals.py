from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Purchase, MonthlyExpense
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ===== PHASE 8: FINANCE ADVANCED AUTOMATIONS =====

@receiver(post_save, sender=Purchase)
def calculate_tax_on_purchase(sender, instance, created, **kwargs):
    """Auto-suggest IVA 21% if amount looks tax-inclusive."""
    if created and instance.amount and instance.amount > 0:
        # Assume amount is tax-inclusive (final price)
        # Base = Amount / 1.21
        # IVA = Amount - Base
        tax_base = instance.amount / Decimal('1.21')
        iva = instance.amount - tax_base
        
        # Only log if IVA is substantial
        if iva > Decimal('100.00'):
            logger.info(
                f"💡 TAX SUGGESTION: Purchase from '{instance.provider.name}' - "
                f"Amount: ${instance.amount:.2f}. "
                f"If tax-inclusive (IVA 21%), Base: ${tax_base:.2f}, IVA: ${iva:.2f}"
            )


@receiver(post_save, sender=MonthlyExpense)
def calculate_next_due_date(sender, instance, created, **kwargs):
    """Auto-calculate next month's due date for recurring expenses."""
    if instance.cost_definition and instance.due_date:
        # Calculate next month
        next_month = (instance.month.month % 12) + 1
        next_year = instance.month.year + (1 if next_month == 1 else 0)
        next_due = instance.due_date.replace(year=next_year, month=next_month)
        
        logger.info(
            f"💡 NEXT DUE: {instance.cost_definition.name} - Next payment due on {next_due.strftime('%Y-%m-%d')}"
        )


# ===== PHASE 10: PURCHASE → STOCK UPDATE =====

from inventory.models import Ingredient

@receiver(post_save, sender=Purchase)
def update_ingredient_stock_on_purchase(sender, instance, created, **kwargs):
    """Auto-update ingredient stock when purchase is received (status change)."""
    # This would require adding a 'received' field or status to Purchase model
    # For now, we'll trigger on creation if description contains ingredient name
    if created and instance.description:
        # Try to find matching ingredient
        matching_ingredients = Ingredient.objects.filter(
            name__icontains=instance.description[:20]
        )
        
        if matching_ingredients.count() == 1:
            ingredient = matching_ingredients.first()
            
            # Would need quantity field in Purchase
            # For now, just log suggestion
            logger.info(
                f"💡 STOCK UPDATE SUGGESTION: Purchase '{instance.description}' might be for ingredient '{ingredient.name}'. "
                f"Consider updating stock manually or via separate receipt process."
            )


# ===== PHASE 8 CONTINUED: FINANCE CATEGORY SUGGESTIONS =====

@receiver(pre_save, sender=Purchase)
def suggest_category_from_description(sender, instance, **kwargs):
    """Auto-suggest purchase category based on description keywords."""
    if not instance.category and instance.description:
        from .models import PurchaseCategory
        desc_lower = instance.description.lower()
        
        # Find category with matching keyword
        all_categories = PurchaseCategory.objects.all()
        for category in all_categories:
            if category.name.lower() in desc_lower:
                logger.info(
                    f"💡 CATEGORY SUGGESTION: Purchase description contains '{category.name}'. "
                    f"Consider setting category to '{category.name}'."
                )
                break
