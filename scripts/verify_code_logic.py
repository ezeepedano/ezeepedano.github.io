import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient
from traceability.services import StockService

def verify_code_logic():
    print("--- Verifying Ingredient Code Logic ---")
    
    # Test Case 1: Ingredient WITH code
    print("\n1. Testing Ingredient WITH Code 'TST'")
    ing_with_code = Ingredient(name="Test Ingredient With Code", code="TST", type="raw_material")
    # We don't save it to DB to avoid polluting, just testing the service logic which needs an object instance
    # But wait, logic might query DB?
    # Service: code = ingredient.code.upper() if ingredient.code else ingredient.name[:3].upper()
    # Then it queries DB for collision: IngredientLot.objects.filter(...)
    
    next_id = StockService.get_next_internal_id(ing_with_code)
    print(f"Generated ID: {next_id}")
    
    if next_id.startswith("MP-TST-"):
        print("SUCCESS: Code used correctly.")
    else:
        print(f"FAILURE: Expected MP-TST-..., got {next_id}")

    # Test Case 2: Ingredient WITHOUT code (Legacy fallback)
    print("\n2. Testing Ingredient WITHOUT Code (Name: 'Legacy Test')")
    ing_no_code = Ingredient(name="Legacy Test", type="raw_material")
    
    next_id_legacy = StockService.get_next_internal_id(ing_no_code)
    print(f"Generated ID: {next_id_legacy}")
    
    if next_id_legacy.startswith("MP-LEG-"):
        print("SUCCESS: Legacy fallback (first 3 letters) used correctly.")
    else:
        print(f"FAILURE: Expected MP-LEG-..., got {next_id_legacy}")

if __name__ == "__main__":
    try:
        verify_code_logic()
    except Exception as e:
        print(f"ERROR: {e}")
