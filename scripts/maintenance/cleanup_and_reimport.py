
import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User
from sales.models import Sale, Customer
from sales.services.importers.tiendanube import TiendaNubeImporter

def run():
    print("--- STARTING MANUAL CLEANUP & RE-IMPORT ---")
    
    # 1. Cleanup
    deleted_sales = Sale.objects.filter(channel='TIENDANUBE').delete()[0]
    print(f"Deleted {deleted_sales} existing Tienda Nube sales.")
    
    # Cleanup bad customers more aggressively
    # We'll just delete customers created by TN (identified by dedup_key prefix 'count' or check source?)
    # Since we don't have a source field on Customer config easily, we rely on the bad data check or orphan check.
    # For now, let's just delete the ones with 'nan' again to be sure.
    c1 = Customer.objects.filter(name__icontains='nan').delete()[0]
    c2 = Customer.objects.filter(billing_address__icontains='nan').delete()[0]
    # Also delete customers with empty names if any
    c3 = Customer.objects.filter(name='').delete()[0]
    print(f"Deleted {c1+c2+c3} suspicious customer records.")

    # 2. Import
    filename = 'ventas-d00115c7-5b32-4e86-8f60-96e49d5aa024.csv'
    if not os.path.exists(filename):
        print(f"ERROR: File {filename} not found!")
        return

    # Try to find test_admin first, else admin, else first
    user = User.objects.filter(username='test_admin').first()
    if not user:
        user = User.objects.filter(username='admin').first()
    if not user:
        user = User.objects.first()
        
    print(f"Importing as user: {user.username}")

    importer = TiendaNubeImporter(user)
    
    with open(filename, 'rb') as f:
        # We need to read it as bytes for the importer, which expects a file-like object
        # The importer does file_obj.seek(0) and read(), so passing the file handle is fine.
        stats = importer.process_file(f)
        print("Import Stats:", stats)

    # 3. Verify
    print("\n--- VERIFICATION ---")
    bad_sales = Sale.objects.filter(channel='TIENDANUBE', buyer_address__icontains='nan').count()
    bad_cust = Customer.objects.filter(name__icontains='nan').count()
    
    print(f"Sales with 'nan' in address: {bad_sales}")
    print(f"Customers with 'nan' in name: {bad_cust}")
    
    if bad_sales == 0 and bad_cust == 0:
        print("SUCCESS: Data is clean.")
    else:
        print("FAILURE: 'nan' still exists.")

if __name__ == '__main__':
    run()
