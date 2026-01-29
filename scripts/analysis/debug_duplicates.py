import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.db.models import Count
from sales.models import Customer
from django.contrib.auth.models import User

def inspect_duplicates():
    users = User.objects.all()
    for user in users:
        count = Customer.objects.filter(user=user).count()
        if count == 0:
            continue
            
        print(f"User: {user.username} (ID: {user.id}) - Customers: {count}")
        
        # Check for similar names manually
        print("   Dumping first 20 names (wrapped in quotes):")
        customers = Customer.objects.filter(user=user).select_related('stats').order_by('name')[:20]
        for c in customers:
             print(f"   '{c.name}' (ID: {c.id})")
             
        # Check specific suspect "ACUA"
        print("   Checking 'ACUA' variants:") 
        acuas = Customer.objects.filter(user=user, name__icontains="ACUA")
        for c in acuas:
            print(f"   MATCH: '{c.name}' (ID: {c.id}) Key: {c.dedup_key}")



if __name__ == '__main__':
    inspect_duplicates()
