
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.models import Sale, Customer

# Check specific sale
try:
    sale = Sale.objects.get(order_id='100')
    print(f"--- SALE #{sale.order_id} ---")
except Sale.DoesNotExist:
    print("SALE #100 NOT FOUND")
    sale = None

if sale:
    print(f"Status: {repr(sale.status)}")
    print(f"Payment Status: {repr(sale.payment_status)}")
    print(f"Shipping Status: {repr(sale.shipping_status)}")
    print(f"Buyer Address: {repr(sale.buyer_address)}")
    print(f"Recipient Name: {repr(sale.recipient_name)}")
    print(f"Recipient Phone: {repr(sale.recipient_phone)}")
    print(f"Buyer Notes: {repr(sale.buyer_notes)}")
    print(f"Seller Notes: {repr(sale.seller_notes)}")
    
    c = sale.customer
    if c:
        print(f"\n--- CUSTOMER {c.name} ---")
        print(f"Email: {repr(c.email)}")
        print(f"Phone: {repr(c.phone)}")
        print(f"Address: {repr(c.billing_address)}")
        print(f"City: {repr(c.city)}")
        print(f"State: {repr(c.state)}")
        print(f"Zip: {repr(c.postal_code)}")
    else:
        print("\nNO CUSTOMER LINKED")
