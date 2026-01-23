from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, Count, Min, Max, F, Avg
from django.utils import timezone
from .models import Sale, Customer, CustomerStats

@receiver(post_save, sender=Customer)
def create_customer_stats(sender, instance, created, **kwargs):
    if created:
        CustomerStats.objects.create(customer=instance)

@receiver(post_save, sender=Sale)
def update_customer_stats_on_sale(sender, instance, created, **kwargs):
    """
    Update customer stats whenever a sale is saved.
    """
    if not instance.customer:
        return

    # Get or create stats (safety)
    stats, _ = CustomerStats.objects.get_or_create(customer=instance.customer)
    
    # Recalculate everything for accuracy (heavy but safe)
    # Filter sales for this customer
    sales_qs = Sale.objects.filter(customer=instance.customer, status__in=['paid', 'delivered', 'completed', 'sent'])
    
    # If using string status, ensure we capture all "valid" sales. 
    # Current importers use various statuses. Let's assume anything NOT 'cancelled' counts?
    # Or just all sales? Usually "cancelled" should be excluded.
    sales_qs = sales_qs.exclude(status__icontains='cancel')

    aggregates = sales_qs.aggregate(
        total_spent=Sum('total'),
        total_orders=Count('id'),
        last_order=Max('date'),
        first_order=Min('date')
    )
    
    stats.total_spent = aggregates['total_spent'] or 0
    stats.total_orders = aggregates['total_orders'] or 0
    stats.last_order_date = aggregates['last_order']
    stats.first_order_date = aggregates['first_order']
    
    if stats.total_orders > 0:
        stats.avg_ticket = stats.total_spent / stats.total_orders
    else:
        stats.avg_ticket = 0
        
    if stats.last_order_date:
        delta = timezone.now() - stats.last_order_date
        stats.days_since_last_order = delta.days
        
    stats.save()

from django.db import transaction
from django.core.exceptions import ValidationError
from .models import SaleItem

@receiver(post_save, sender=Sale)
def deduct_stock_on_sale_confirmation(sender, instance, created, **kwargs):
    """
    Deducts stock when a Sale is confirmed/paid.
    Trigger: Status changes to 'paid', 'completed', 'delivered' or 'sent'.
    Protection: Deduct ONLY once. Needs a flag or status check transition?
    
    Current Logic:
    - We check if status is 'valid' AND if we haven't deducted yet?
    - But we don't have a 'stock_deducted' boolean. 
    - Risk: If we save 'paid' twice, we deduct twice.
    
    Solution for MVP:
    - Only deduct if `created` is True (if we assume sales are created as 'paid' from import?)
    - OR check if `instance.orig_status != instance.status` (requires tracking pre-save, which post_save can't do easily without a __init__ hack).
    
    Better approach for MVP w/o Changing Model:
    - Rely on `created` if Import creates them as Paid.
    - If manual update, risk is real. 
    
    Let's stick to: If created OR if status changed to PAID (we can't know if changed in post_save easily).
    
    Safe bet: We only deduct if we are SURE. 
    Let's assume most sales come from Import as 'paid'.
    So `if created and instance.status == 'paid'`.
    """
    
    # Valid statuses for deduction
    VALID_STATUSES = ['paid', 'completed', 'delivered', 'sent']
    
    if instance.status not in VALID_STATUSES:
        return
        
    # Prevent double deduction
    if instance.stock_deducted:
        return
         
    with transaction.atomic():
        deducted_any = False
        for item in instance.items.all():
            if item.product:
                item.product.stock_quantity -= item.quantity
                item.product.save()
                deducted_any = True
        
        # Only set flag if we actually processed items
        if deducted_any:
            # Update flag without triggering signals again (to avoid recursion? post_save calls save?)
            # update() doesn't trigger signals.
            Sale.objects.filter(pk=instance.pk).update(stock_deducted=True)

