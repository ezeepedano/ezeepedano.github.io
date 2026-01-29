import os
import django
import sys
import json
from datetime import date

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from dashboard.services.executive_metrics import ExecutiveMetricsService

print("--- TESTING DASHBOARD SERVICES ---")

# 1. Test KPIs with Default Date
print("\n1. Testing get_kpis({'date__gte': '2024-01-01'})...")
try:
    data = ExecutiveMetricsService.get_kpis({'date__gte': '2024-01-01'})
    print("SUCCESS")
    print(f"Revenue: {data.get('revenue')}")
    print(f"Orders: {data.get('orders')}")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()

# 2. Test Sales Trends (Weekly, Last 30)
print("\n2. Testing get_sales_trends(bucket='week', window=30)...")
try:
    data = ExecutiveMetricsService.get_sales_trends({'date__gte': '2024-01-01'}, bucket='week', window=30)
    print("SUCCESS")
    print(f"Points: {len(data.get('points', []))}")
    print(f"Summary: {data.get('summary')}")
except Exception as e:
    print(f"FAIL: {e}")
    traceback.print_exc()

# 3. Test Sales Trends (Monthly, All Time)
print("\n3. Testing get_sales_trends(bucket='month', window=9999)...")
try:
    # Mimic "All Time" where date filters might be empty
    data = ExecutiveMetricsService.get_sales_trends({}, bucket='month', window=9999)
    print("SUCCESS")
    print(f"Points: {len(data.get('points', []))}")
except Exception as e:
    print(f"FAIL: {e}")
    traceback.print_exc()

print("\n--- TEST COMPLETE ---")
