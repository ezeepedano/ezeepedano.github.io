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
        customer=customer,
    ).exclude(status__icontains='cancel')

    aggregates = sales_qs.aggregate(
        total_spent=Sum('total'),
        total_orders=Count('id'),
        total_paid=Sum('paid_amount'),
        last_order=Max('date'),
        first_order=Min('date'),
        max_ticket=Max('total'),
    )

    # Units sold via items (one extra query)
    from .models import SaleItem
    units_total = SaleItem.objects.filter(
        sale__in=sales_qs,
    ).aggregate(t=Sum('quantity'))['t'] or 0

    total_spent = aggregates['total_spent'] or Decimal('0')
    total_orders = aggregates['total_orders'] or 0
    total_paid = aggregates['total_paid'] or Decimal('0')

    stats.total_spent = total_spent
    stats.total_orders = total_orders
    stats.total_units = int(units_total)
    stats.max_ticket = aggregates['max_ticket'] or Decimal('0')
    stats.last_order_date = aggregates['last_order']
    stats.first_order_date = aggregates['first_order']
    stats.avg_ticket = (total_spent / total_orders) if total_orders > 0 else Decimal('0')

    if stats.last_order_date:
        delta = timezone.now() - stats.last_order_date
        # Future-dated test data can produce negative deltas; clamp to 0.
        stats.days_since_last_order = max(0, delta.days)
    else:
        stats.days_since_last_order = 999

    # =========================================================================
    # 1b. RFM SCORES (1–5 scale, larger = better)
    # =========================================================================
    # Recency: smaller days_since_last → higher score
    days = stats.days_since_last_order
    if days <= 30:    stats.r_score = 5
    elif days <= 60:  stats.r_score = 4
    elif days <= 90:  stats.r_score = 3
    elif days <= 180: stats.r_score = 2
    else:             stats.r_score = 1

    if total_orders >= 10:  stats.f_score = 5
    elif total_orders >= 5: stats.f_score = 4
    elif total_orders >= 3: stats.f_score = 3
    elif total_orders >= 2: stats.f_score = 2
    elif total_orders >= 1: stats.f_score = 1
    else:                   stats.f_score = 0

    spent = float(total_spent)
    if spent >= 200000:   stats.m_score = 5
    elif spent >= 100000: stats.m_score = 4
    elif spent >= 50000:  stats.m_score = 3
    elif spent >= 20000:  stats.m_score = 2
    elif spent > 0:       stats.m_score = 1
    else:                 stats.m_score = 0

    # =========================================================================
    # 2. AUTO-ASSIGN CUSTOMER SEGMENT (Spanish labels — match UI)
    # =========================================================================
    old_segment = stats.segment
    if total_orders == 0:
        stats.segment = 'Nuevo'
    elif spent >= 200000 and days <= 90:
        stats.segment = 'VIP'
    elif total_orders >= 5 and days <= 90:
        stats.segment = 'Fiel'
    elif days > 180:
        stats.segment = 'Dormido'
    elif days > 90:
        stats.segment = 'En riesgo'
    elif total_orders == 1 and days <= 60:
        stats.segment = 'Nuevo'
    else:
        stats.segment = 'Recurrente'

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
