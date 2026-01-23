
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.models import Sale
from django.contrib.auth.models import User

print(f"Total Sales in DB: {Sale.objects.count()}")

# Group by User and Channel
for u in User.objects.all():
    print(f"\nUser: {u.username} (ID: {u.id})")
    user_sales = Sale.objects.filter(user=u)
    print(f"  Total: {user_sales.count()}")
    
    for channel in ['TIENDANUBE', 'MERCADOLIBRE', 'WHOLESALE']:
        count = user_sales.filter(channel=channel).count()
        print(f"  - {channel}: {count}")
        
    # Check for 'TIENDANUBE' specifically
    tn = user_sales.filter(channel='TIENDANUBE')
    if tn.exists():
        print("  --> LATEST 5 TN SALES:")
        for s in tn.order_by('-date')[:5]:
            print(f"      #{s.order_id} | {s.date} | {s.channel} | Owner: {s.user.username}")

print("\n--- Sales with NO user ---")
orphans = Sale.objects.filter(user__isnull=True)
print(f"Count: {orphans.count()}")
if orphans.exists():
    for s in orphans[:5]:
        print(f"  #{s.order_id} | {s.channel}")
