import os
import django
import sys

# Setup Django environment
sys.path.append(r'c:\Users\Giuliana\OneDrive - alumnos.iua.edu.ar\JKGE 2025\ERP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Product  # noqa: E402
from decimal import Decimal  # noqa: E402

def diagnose_product_cost(product_name_part):
    products = Product.objects.filter(name__icontains=product_name_part)
    if not products.exists():
        print(f"No product found containing '{product_name_part}'")
        return

    for product in products:
        print(f"\n--- Diagnosing Product: {product.name} (ID: {product.id}) ---")
        print(f"Unit Measure: {product.unit_measure}")
        print(f"Net Weight: {product.net_weight}")
        print(f"Current Cost Price: ${product.cost_price}")

        total_formula_cost = 0
        total_formula_weight = 0
        total_supply_cost = 0

        recipes = product.recipes.all()
        if not recipes.exists():
            print("No recipes found for this product.")
            continue

        print(f"\nRecipes ({recipes.count()} items):")
        for recipe in recipes:
            ing = recipe.ingredient
            qty = recipe.quantity
            print(f" - Ingredient: {ing.name} (ID: {ing.id})")
            print(f"   Type: {ing.type}")
            print(f"   Unit: {ing.unit} | Cost/Unit: ${ing.cost_per_unit}")
            print(f"   Recipe Qty: {qty}")

            if ing.type == 'raw_material':
                # Replicating Update Logic
                factor = Decimal('1')
                if ing.unit == product.unit_measure:
                    factor = Decimal('1')
                    print("   Conversion: Same unit")
                elif ing.unit == 'kg' and product.unit_measure == 'g':
                    factor = Decimal('0.001')
                    print("   Conversion: kg -> g (0.001)")
                elif ing.unit == 'g' and product.unit_measure == 'kg':
                    factor = Decimal('1000')
                    print("   Conversion: g -> kg (1000)")
                elif ing.unit == 'l' and product.unit_measure == 'ml':
                    factor = Decimal('0.001')
                    print("   Conversion: l -> ml (0.001)")
                elif ing.unit == 'ml' and product.unit_measure == 'l':
                    factor = Decimal('1000')
                    print("   Conversion: ml -> l (1000)")
                else:
                    print(f"   Conversion: UNMATCHED ({ing.unit} to {product.unit_measure}) - Factor 1")

                unit_cost_aligned = ing.cost_per_unit * factor
                line_cost = qty * unit_cost_aligned
                total_formula_cost += line_cost
                total_formula_weight += qty
                print(f"   Line Cost: ${line_cost} (Qty {qty} * Aligned Cost {unit_cost_aligned})")

            elif ing.type == 'supply':
                line_cost = qty * ing.cost_per_unit
                total_supply_cost += line_cost
                print(f"   Line Cost: ${line_cost} (Supply)")

        print("-" * 30)
        print(f"Total Formula Weight: {total_formula_weight}")
        
        final_formula_cost = 0
        if total_formula_weight > 0:
            cost_per_unit_weight = total_formula_cost / total_formula_weight
            final_formula_cost = cost_per_unit_weight * product.net_weight
            print(f"Calculated Cost/Weight Unit: ${cost_per_unit_weight}")
            print(f"Scaled Formula Cost: ${final_formula_cost} (Cost/Unit * NetWeight {product.net_weight})")
        else:
            print("Total Formula Weight is 0. Cannot scale.")

        final_total = final_formula_cost + total_supply_cost
        print(f"\nFINAL CALCULATED COST: ${final_total}")

if __name__ == "__main__":
    diagnose_product_cost("Citrato")
