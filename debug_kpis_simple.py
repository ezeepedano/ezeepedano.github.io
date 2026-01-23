import os
import django
import sys

# Add project root to sys path
sys.path.append(os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from dashboard.services.executive_metrics import ExecutiveMetricsService
from sales.models import Sale

print("--- DEBUG START ---")
print(f"Total Sales Count: {Sale.objects.count()}")

qs = Sale.objects.all()
try:
    from django.db.models import Sum, Count
    agg = qs.aggregate(rev=Sum('total'), count=Count('id'))
    print(f"Agg result: {agg}")
except Exception as e:
    print(f"Agg failed: {e}")

print("--- Service Call ---")
try:
    kpis = ExecutiveMetricsService.get_kpis({})
    print(f"KPIs: {kpis}")
except Exception as e:
    print(f"Service failed: {e}")
