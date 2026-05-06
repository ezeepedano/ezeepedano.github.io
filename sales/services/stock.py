"""
Stock Service Module

Centralizes all stock deduction and restoration logic in one place.
Used by views (manual sales) and importers (bulk imports) alike.

Author: ERP Development Team
Updated: 2026-02-16
"""

import logging
from django.db import transaction
from django.db.models import F

from inventory.models import Product

logger = logging.getLogger(__name__)


class StockService:
    """
    Centralized service for all stock operations.

    Replaces the scattered stock logic previously in:
    - sales/views.py (sync_sale_stock)
    - sales/signals.py (deduct_stock_on_sale_confirmation)
    - sales/services/importers/tiendanube.py (inline deduction)
    """

    @staticmethod
    @transaction.atomic
    def deduct_sale_stock(sale):
        """
        Deduct stock for all items in a sale.

        Args:
            sale: Sale instance with items to process.

        Returns:
            int: Number of products whose stock was updated.
        """
        if sale.stock_deducted:
            logger.warning(
                f"Stock already deducted for Sale #{sale.order_id}, skipping."
            )
            return 0

        updated = 0
        for item in sale.items.select_related('product').all():
            if item.product:
                # Atomic, race-free decrement at the DB level
                Product.objects.filter(pk=item.product.pk).update(
                    stock_quantity=F('stock_quantity') - item.quantity
                )
                updated += 1

        if updated:
            sale.stock_deducted = True
            sale.save(update_fields=['stock_deducted'])
            logger.info(
                f"Stock deducted for Sale #{sale.order_id} ({updated} products)"
            )

        return updated

    @staticmethod
    @transaction.atomic
    def restore_sale_stock(sale):
        """
        Restore (add back) stock for all items in a sale.
        Typically used before editing a sale or on cancellation.

        Args:
            sale: Sale instance with items to restore.

        Returns:
            int: Number of products whose stock was restored.
        """
        if not sale.stock_deducted:
            logger.warning(
                f"Stock not previously deducted for Sale #{sale.order_id}, "
                f"skipping restore."
            )
            return 0

        updated = 0
        for item in sale.items.select_related('product').all():
            if item.product:
                Product.objects.filter(pk=item.product.pk).update(
                    stock_quantity=F('stock_quantity') + item.quantity
                )
                updated += 1

        if updated:
            sale.stock_deducted = False
            sale.save(update_fields=['stock_deducted'])
            logger.info(
                f"Stock restored for Sale #{sale.order_id} ({updated} products)"
            )

        return updated

    @staticmethod
    @transaction.atomic
    def deduct_item_stock(product, quantity):
        """
        Deduct stock for a single product/quantity.
        Used by importers when processing individual items.

        Args:
            product: Product instance.
            quantity: Number of units to deduct.
        """
        if product:
            Product.objects.filter(pk=product.pk).update(
                stock_quantity=F('stock_quantity') - quantity
            )

