import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient
from traceability.models import IngredientLot
from production.models import BillOfMaterial

def debug_stock():
    print("--- INGREDIENTS ---")
    for ing in Ingredient.objects.all():
        print(f"ID: {ing.id}, Name: {ing.name}, Type: {ing.type}, StockQty (on model): {ing.stock_quantity}")

    print("\n--- INGREDIENT LOTS (Stock) ---")
    for lot in IngredientLot.objects.all():
        print(f"Lot ID: {lot.id}, InternalID: {lot.internal_id}, Ingredient: {lot.ingredient.name} (ID: {lot.ingredient.id}), Qty: {lot.quantity_current}, Active: {lot.is_active}")

    print("\n--- BOM: citramagnrj ---")
    try:
        # Try to find by code or similar
        boms = BillOfMaterial.objects.filter(code__icontains='citramagnrj')
        if not boms.exists():
             print("No BOM found with code 'citramagnrj', searching all...")
             boms = BillOfMaterial.objects.all()

        for bom in boms:
            print(f"BOM: {bom.name} (Code: {bom.code})")
            for line in bom.lines.all():
                print(f"  - Line: Ing: {line.ingredient.name} (ID: {line.ingredient.id}), Qty: {line.quantity}")
                
                # Check specific stock for this line
                lots = IngredientLot.objects.filter(ingredient=line.ingredient, is_active=True)
                total_stock = sum(lot.quantity_current for lot in lots)
                print(f"    -> AVAILABLE STOCK CALCULATED: {total_stock}")

    except Exception as e:
        print(f"Error checking BOMs: {e}")

if __name__ == "__main__":
    debug_stock()
