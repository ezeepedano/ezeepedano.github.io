
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from sales.models import SaleItem

def diagnose():
    unlinked = SaleItem.objects.filter(product__isnull=True)
    count = unlinked.count()
    print(f"Unlinked Items Count: {count}")
    
    if count == 0:
        return

    print("\nSample Unlinked Items (SKU | Title):")
    for item in unlinked[:20]:
        print(f"SKU: '{item.sku}' | Title: '{item.product_title}'")

if __name__ == "__main__":
    diagnose()
