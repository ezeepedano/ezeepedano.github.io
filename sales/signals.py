"""
Sales Signals Module

Handles automatic side-effects when Sale and Customer objects are saved.
Consolidated from the original 6+ individual signal handlers into 2 efficient ones.

Author: ERP Development Team
Updated: 2026-02-16
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum, Count, Min, Max
from django.utils import timezone
from decimal import Decimal
from datetime import date
import logging

from .models import Sale, Customer, CustomerStats

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def create_customer_stats(sender, instance, created, **kwargs):
    """Auto-create CustomerStats when a new Customer is created."""
    if created:
        CustomerStats.objects.get_or_create(customer=instance)


@receiver(post_save, sender=Sale)
def update_customer_on_sale(sender, instance, created, **kwargs):
    """
    Consolidated signal: updates ALL customer-related data when a sale is saved.

    Replaces the old separate signals:
    - update_customer_stats_on_sale
    - auto_assign_customer_segment
    - check_debt_alert
    - notify_sales_team_on_high_debt (merged into debt check)
    - autocomplete_shipping_from_last_sale
    """
    customer = instance.customer
    if not customer:
        return

    # =========================================================================
    # 1. RECALCULATE CUSTOMER STATS (single query batch)
    # =========================================================================
    stats, _ = CustomerStats.objects.get_or_create(customer=customer)

    sales_qs = Sale.objects.filter(
        customer=customer
    ).exclude(
        status__icontains='cancel'
    )

    aggregates = sales_qs.aggregate(
        total_spent=Sum('total'),
        total_orders=Count('id'),
        total_paid=Sum('paid_amount'),
        last_order=Max('date'),
        first_order=Min('date'),
    )

    total_spent = aggregates['total_spent'] or Decimal('0')
    total_orders = aggregates['total_orders'] or 0
    total_paid = aggregates['total_paid'] or Decimal('0')

    stats.total_spent = total_spent
    stats.total_orders = total_orders
    stats.last_order_date = aggregates['last_order']
    stats.first_order_date = aggregates['first_order']
    stats.avg_ticket = (total_spent / total_orders) if total_orders > 0 else 0

    if stats.last_order_date:
        delta = timezone.now() - stats.last_order_date
        stats.days_since_last_order = delta.days
    else:
        stats.days_since_last_order = 999

    # =========================================================================
    # 2. AUTO-ASSIGN CUSTOMER SEGMENT (uses data already computed above)
    # =========================================================================
    days_since_last = stats.days_since_last_order or 999

    old_segment = stats.segment
    if total_spent > 100000:  # > 100k ARS
        stats.segment = 'VIP'
    elif total_orders >= 5 and days_since_last < 90:
        stats.segment = 'LOYAL'
    elif days_since_last > 180:
        stats.segment = 'DORMANT'
    else:
        stats.segment = 'ACTIVE'

    if old_segment and old_segment != stats.segment:
        logger.info(
            f"Customer {customer.name} segment: {old_segment} → {stats.segment}"
        )

    stats.save()

    # =========================================================================
    # 3. DEBT CHECK (single alert, two thresholds — uses aggregates above)
    # =========================================================================
    total_debt = total_spent - total_paid

    CRITICAL_DEBT = Decimal('100000')
    WARNING_DEBT = Decimal('50000')

    if total_debt > CRITICAL_DEBT:
        logger.error(
            f"CRITICAL DEBT: Customer {customer.name} has ${total_debt} "
            f"in debt (>${CRITICAL_DEBT}). Block new sales until payment."
        )
    elif total_debt > WARNING_DEBT:
        logger.warning(
            f"DEBT ALERT: Customer {customer.name} has ${total_debt} "
            f"in debt (>${WARNING_DEBT})"
        )

    # =========================================================================
    # 4. AUTO-COMPLETE SHIPPING (only on creation)
    # =========================================================================
    if created and customer:
        last_sale = Sale.objects.filter(
            customer=customer,
            status__in=['Confirmado', 'Entregado', 'Listo para enviar']
        ).exclude(pk=instance.pk).order_by('-date').first()

        if last_sale:
            fields_to_update = []
            if not instance.city and last_sale.city:
                instance.city = last_sale.city
                fields_to_update.append('city')
            if not instance.province and last_sale.province:
                instance.province = last_sale.province
                fields_to_update.append('province')

            if fields_to_update:
                Sale.objects.filter(pk=instance.pk).update(
                    **{f: getattr(instance, f) for f in fields_to_update}
                )
                logger.info(
                    f"Auto-completed shipping for Sale #{instance.order_id} "
                    f"from last sale #{last_sale.order_id}"
                )
