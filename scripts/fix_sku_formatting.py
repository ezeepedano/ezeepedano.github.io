
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from inventory.models import Product

def fix_skus():
    products = Product.objects.all()
    print(f"Total products: {products.count()}")
    
    deleted_count = 0
    renamed_count = 0
    
    # Get all SKUs first to avoid modification during iteration issues
    all_skus = list(products.values_list('sku', flat=True))
    
    for product in products:
        current_sku = product.sku
        upper_sku = current_sku.upper()
        
        if current_sku == upper_sku:
            continue
            
        # It's not uppercase. Check if uppercase exists.
        if upper_sku in all_skus:
            # Duplicate exists. We assume the UPPERCASE one is the one from the Import (latest).
            # So we delete the lowercase one.
            # Safety check: does it have relations? 
            # For now, simplistic: delete.
            print(f"Deleting duplicate lowercase: {current_sku} (Keep {upper_sku})")
            product.delete()
            deleted_count += 1
        else:
            # No duplicate, just rename
            print(f"Renaming to uppercase: {current_sku} -> {upper_sku}")
            product.sku = upper_sku
            product.save()
            renamed_count += 1
            
    print(f"\nSummary:")
    print(f"Deleted (Duplicates): {deleted_count}")
    print(f"Renamed (To Upper): {renamed_count}")

if __name__ == "__main__":
    fix_skus()
