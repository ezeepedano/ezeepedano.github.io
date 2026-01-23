from dashboard.services.executive_metrics import ExecutiveMetricsService
from sales.models import Sale
from django.db.models import Sum, Count

print("--- DIAGNOSTIC START ---")
count = Sale.objects.count()
print(f"Total Sales in DB: {count}")

print("Running get_kpis({}) (All Time)...")
try:
    data = ExecutiveMetricsService.get_kpis({})
    print(f"Revenue: {data.get('revenue')}")
    print(f"Orders: {data.get('orders')}")
    print(f"Units: {data.get('units')}")
    print(f"Full Data: {data}")
except Exception as e:
    print(f"Service Error: {e}")

print("--- RAW AGGREGATION CHECK ---")
qs = Sale.objects.all()
rev = qs.aggregate(s=Sum('total'))['s']
cnt = qs.count()
print(f"Raw Revenue: {rev}")
print(f"Raw Count: {cnt}")
print("--- DIAGNOSTIC END ---")
