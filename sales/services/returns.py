"""
Sales Returns / RMA Service.

Encapsulates the business rules around posting a SaleReturn:
1) Restore product stock atomically (F() expressions, no read-modify-write).
2) Reverse the proportional `paid_amount` on the original Sale and step
   the payment status back if the refund tips it below the total.

All mutations happen inside a single ``transaction.atomic()`` block so a
partial failure leaves the books consistent.
"""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from inventory.models import Product
from sales.models import SaleReturn

logger = logging.getLogger(__name__)


class ReturnService:
    """Process a SaleReturn end-to-end."""

    @staticmethod
    @transaction.atomic
    def process(return_obj: SaleReturn) -> SaleReturn:
        """Mark a return as POSTED and apply its side effects.

        Idempotent: a return already in POSTED state is returned unchanged.
        """
        if return_obj.status == 'POSTED':
            logger.info(
                "ReturnService.process noop: SaleReturn #%s already POSTED.",
                return_obj.pk,
            )
            return return_obj

        if return_obj.status not in ('DRAFT', 'APPROVED'):
            raise ValidationError(
                {'status': "Solo se pueden procesar devoluciones en estado Borrador o Aprobada."}
            )

        sale = return_obj.sale
        # Lock the sale row to prevent concurrent payment edits during refund.
        sale = sale.__class__.objects.select_for_update().get(pk=sale.pk)

        refund_total = Decimal('0')

        for item in return_obj.items.select_related('sale_item__product').all():
            sale_item = item.sale_item
            qty = int(item.quantity or 0)
            if qty <= 0:
                continue
            if qty > sale_item.quantity:
                raise ValidationError({
                    'items': f"No se puede devolver {qty} unidades de "
                             f"{sale_item.product_title}: la venta original tiene {sale_item.quantity}."
                })

            # 1) Atomic stock restore (F expression, no race).
            if item.restocked and sale_item.product_id:
                Product.objects.filter(pk=sale_item.product_id).update(
                    stock_quantity=F('stock_quantity') + qty
                )

            # 2) Accumulate refund amount (proportional to qty).
            refund_total += (sale_item.unit_price or Decimal('0')) * qty

        # 3) Reverse paid_amount + step status back if needed.
        if refund_total > 0:
            new_paid = (sale.paid_amount or Decimal('0')) - refund_total
            if new_paid < 0:
                new_paid = Decimal('0')
            sale.paid_amount = new_paid

            sale_total = sale.total or Decimal('0')
            if new_paid <= 0:
                sale.payment_status = 'PENDING'
            elif new_paid < sale_total:
                sale.payment_status = 'PARTIAL'
            else:
                sale.payment_status = 'PAID'

            sale.save(update_fields=['paid_amount', 'payment_status', 'updated_at'])

        # 4) Mark return as posted.
        return_obj.refund_amount = refund_total
        return_obj.status = 'POSTED'
        return_obj.save(update_fields=['refund_amount', 'status', 'updated_at'])

        logger.info(
            "SaleReturn #%s posted: sale=%s refund=%s",
            return_obj.pk, sale.pk, refund_total,
        )
        return return_obj
