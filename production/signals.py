"""
Production Signals Module

Automatically recalculates BOM cost and updates linked product cost_price
when a BomLine is created, updated, or deleted.

Author: ERP Development Team
Updated: 2026-02-18
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import BomLine

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BomLine)
@receiver(post_delete, sender=BomLine)
def recalculate_bom_cost(sender, instance, **kwargs):
    """
    Recalculate BOM cost and update all linked product cost_prices
    whenever a BOM line is created, modified, or deleted.
    """
    bom = instance.bom

    try:
        new_cost = bom.calculate_cost()
    except Exception as e:
        logger.error(f"Error calculating BOM cost for '{bom}': {e}")
        return

    # Update products linked via M2M (new relation)
    updated_products = []
    for product in bom.products.all():
        if product.cost_price != new_cost:
            old_cost = product.cost_price
            product.cost_price = new_cost
            product.save(update_fields=['cost_price'])
            updated_products.append(product)
            logger.info(
                f"Product '{product.sku}' cost updated: "
                f"${old_cost} → ${new_cost} (BOM: {bom.name})"
            )

    # Update product linked via FK (legacy relation)
    if bom.product and bom.product not in updated_products:
        if bom.product.cost_price != new_cost:
            old_cost = bom.product.cost_price
            bom.product.cost_price = new_cost
            bom.product.save(update_fields=['cost_price'])
            logger.info(
                f"Product '{bom.product.sku}' cost updated: "
                f"${old_cost} → ${new_cost} (BOM: {bom.name})"
            )
