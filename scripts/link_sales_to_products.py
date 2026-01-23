
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from sales.models import SaleItem
from inventory.models import Product

def link_items():
    print("Starting linking process...")
    
    # 1. Fetch all products into a dictionary for fast lookup
    # Normalize keys to lowercase for case-insensitive matching
    products_map = {p.sku.lower(): p for p in Product.objects.all()}
    print(f"Loaded {len(products_map)} products.")
    
    # 2. Fetch unlinked items
    unlinked_items = SaleItem.objects.filter(product__isnull=True)
    count = unlinked_items.count()
    print(f"Found {count} unlinked sale items.")
    
    linked_count = 0
    sku_mismatch_count = 0
    
    batch = []
    BATCH_SIZE = 1000
    
    for item in unlinked_items:
        if not item.sku:
            continue
            
        sku_clean = item.sku.strip().lower()
        
        if sku_clean in products_map:
            item.product = products_map[sku_clean]
            # Optional: Normalize SKU on item too
            item.sku = sku_clean 
            # We add to batch for bulk_update if we wanted, but bulk_update 
            # with relation setting can be tricky. save() is safer for now 
            # unless volume is huge. 4000 is okay for individual saves or batch.
            batch.append(item)
            linked_count += 1
        else:
            sku_mismatch_count += 1
            # print(f"Warning: SKU not found for item {item.product_title} (SKU: {item.sku})")

        if len(batch) >= BATCH_SIZE:
             SaleItem.objects.bulk_update(batch, ['product', 'sku'])
             print(f"Linked batch of {len(batch)}...")
             batch = []
             
    if batch:
        SaleItem.objects.bulk_update(batch, ['product', 'sku'])
        print(f"Linked final batch of {len(batch)}.")

    print(f"\nSummary:")
    print(f"Successfully Linked: {linked_count}")
    print(f"SKUs Not Found: {sku_mismatch_count}")

if __name__ == "__main__":
    link_items()
