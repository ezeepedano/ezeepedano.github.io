import os
import django
import sys
from decimal import Decimal
from datetime import date

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient
from traceability.models import IngredientLot
from django.db.models import Sum

def sync_stock():
    print("--- STARTING STOCK SYNC ---")
    
    ingredients = Ingredient.objects.all()
    created_count = 0
    
    for ing in ingredients:
        # Calculate total in lots
        total_lots = IngredientLot.objects.filter(ingredient=ing, is_active=True).aggregate(t=Sum('quantity_current'))['t'] or Decimal('0')
        
        # Check legacy stock
        legacy_stock = ing.stock_quantity # This is a Decimal field
        
        diff = legacy_stock - total_lots
        
        if diff > 0.001:
            print(f"Syncing {ing.name} (User: {ing.user}): Legacy={legacy_stock}, Lots={total_lots}. Creating adjustment lot for {diff} {ing.unit}")
            
            # Create a manual lot to cover the difference
            # We construct a unique ID based on date
            count = IngredientLot.objects.filter(ingredient=ing).count() + 1
            internal_id = f"ADJ-{ing.id}-{date.today().strftime('%Y%m%d')}-{count}"
            
            IngredientLot.objects.create(
                user=ing.user,
                ingredient=ing,
                internal_id=internal_id,
                quantity_initial=diff,
                quantity_current=diff,
                supplier_lot="AJUSTE-MANUAL-LEGACY",
                received_date=date.today(),
                is_active=True,
                is_wasted=False
            )
            created_count += 1
            
        elif diff < -0.001:
            print(f"WARNING: {ing.name} has LESS physical stock ({legacy_stock}) than Lots ({total_lots}). Skipping (manual correction needed).")
            
    print(f"--- SYNC COMPLETE. Created {created_count} adjustment lots. ---")

if __name__ == "__main__":
    sync_stock()
