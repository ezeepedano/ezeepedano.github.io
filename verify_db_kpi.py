import os
import django
import sys

# Add project root to sys path
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from sales.models import Sale
from django.db.models import Sum

print("--- DB VERIFY START ---")
count = Sale.objects.count()
print(f"COUNT={count}")

agg = Sale.objects.aggregate(total=Sum('total'))
print(f"SUM={agg['total']}")

# Check first sale
first = Sale.objects.first()
if first:
    print(f"FIRST_SALE_ID={first.pk}")
    print(f"FIRST_SALE_DATE={first.date}")
else:
    print("NO SALES FOUND")
print("--- DB VERIFY END ---")
