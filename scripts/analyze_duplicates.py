import os
import django
import sys
from django.db.models import Sum

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient
from traceability.models import IngredientLot

def analyze_duplicates():
    # Helper to get stock
    def get_stock(ing):
        return IngredientLot.objects.filter(ingredient=ing, is_active=True).aggregate(t=Sum('quantity_current'))['t'] or 0

    # Group by name
    by_name = {}
    for ing in Ingredient.objects.all():
        name_lower = ing.name.lower().strip()
        if name_lower not in by_name:
            by_name[name_lower] = []
        by_name[name_lower].append(ing)

    print("--- DUPLICATE ANALYSIS ---")
    for name, ingredients in by_name.items():
        if len(ingredients) > 1:
            print(f"Name: '{name}'")
            for ing in ingredients:
                stock = get_stock(ing)
                print(f"  - ID: {ing.id}, Name: '{ing.name}', Type: {ing.type}, Cost: {ing.cost_per_unit}, Stock: {stock}")

if __name__ == "__main__":
    analyze_duplicates()
