
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.models import Customer

bad_customers = Customer.objects.filter(name__icontains='nan')
print(f"Found {bad_customers.count()} customers with 'nan' in name:")
for c in bad_customers:
    print(f"ID: {c.id}, Name: '{c.name}', Email: '{c.email}'")

print("\nChecking exact 'nan':")
exact_nan = Customer.objects.filter(name__iexact='nan')
print(f"Exact 'nan' matches: {exact_nan.count()}")
