import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.models import Customer
from django.contrib.auth.models import User

def inspect_acua():
    try:
        user = User.objects.get(id=2)
    except User.DoesNotExist:
        print("User ID 2 not found!")
        return

    print(f"Checking duplicates for user: {user.username} (ID: {user.id})")
    
    with open('acua_debug.log', 'w', encoding='utf-8') as f:
        f.write(f"Checking duplicates for user: {user.username} (ID: {user.id})\n")
        # Check specific suspect "ACUA"
        f.write("Checking 'ACUA' variants:\n") 
        acuas = Customer.objects.filter(user=user, name__icontains="ACUA")
        for c in acuas:
            f.write(f"ID: {c.id}\n")
            f.write(f"Name: '{c.name}'\n")
            f.write(f"Repr: {repr(c.name)}\n")
            f.write(f"DedupKey: {c.dedup_key}\n")
            f.write("-" * 20 + "\n")
    print("Done writing to acua_debug.log")

if __name__ == '__main__':
    inspect_acua()
