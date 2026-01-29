import os
import django
import sys
from decimal import Decimal

# Add project root to sys path
sys.path.append(os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from dashboard.services.executive_metrics import ExecutiveMetricsService
from sales.models import Sale

print(f"Count of Sales: {Sale.objects.count()}")

print("\n--- Running get_kpis({}) ---")
try:
    data = ExecutiveMetricsService.get_kpis({})
    print("Result:")
    print(f"Revenue: {data.get('revenue')}")
    print(f"Orders: {data.get('orders')}")
    print(f"Units: {data.get('units')}")
    print(f"Full Data: {data}")
except Exception as e:
    print(f"Error: {e}")
