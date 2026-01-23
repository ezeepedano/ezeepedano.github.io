
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.models import Sale
from django.contrib.auth.models import User

users = User.objects.all()
for u in users:
    print(f"--- Debugging for user: {u.username} ---")

    # Simulate ALL view
    all_sales = Sale.objects.filter(user=u).order_by('-date')
    print(f"Total Sales (ALL): {all_sales.count()}")

    # Check channel breakdown in ALL
    tn_in_all = all_sales.filter(channel='TIENDANUBE').count()
    meli_in_all = all_sales.filter(channel='MERCADOLIBRE').count()
    ws_in_all = all_sales.filter(channel='WHOLESALE').count()
    print(f" Breakdown in ALL -> TN: {tn_in_all}, MELI: {meli_in_all}, WS: {ws_in_all}")

    # Explicit TN filter
    tn_sales = Sale.objects.filter(user=u, channel='TIENDANUBE')
    print(f"Total Sales (Channel=TN): {tn_sales.count()}")
    print("-" * 20)
