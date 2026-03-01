from production.models import BillOfMaterial, BomLine
from inventory.models import Product, Ingredient

def run():
    print("Fixing Citrato Data...")
    
    # 1. Fix Formula (BOM)
    # Search by name/code seen in screenshot
    boms = BillOfMaterial.objects.filter(name__icontains="citra")
    for bom in boms:
        print(f"Checking BOM: {bom.name}")
        
        # Determine if this is the one with 30/63/7
        # We'll just fix known issues if they look like 30, 63, etc.
        
        # Fix Base Quantity
        # If it's 100.0 (user might have tried 100) or 1.0 (default)
        # We want 0.100 (100g in kg)
        # Re-reading: User had "100.00" in Base Quantity in one screenshot?
        # No, user had 0 probably.
        # Let's set it to 0.1 (100g)
        bom.quantity = 0.1
        bom.save()
        print(f"  -> Set BOM Base Quantity to 0.1")
        
        for line in bom.lines.all():
            if line.ingredient:
                name = line.ingredient.name.lower()
                qty = line.quantity
                
                # Check for Sulfato (30 -> 0.03)
                if "sulfato" in name and qty >= 1:
                     # Assume input was grams, convert to kg
                     new_qty = qty / 1000
                     line.quantity = new_qty
                     line.save()
                     print(f"  -> Fixed {line.ingredient.name}: {qty} -> {new_qty}")
                
                # Check for Malto (63 -> 0.063)
                elif "malto" in name and qty >= 1:
                     new_qty = qty / 1000
                     line.quantity = new_qty
                     line.save()
                     print(f"  -> Fixed {line.ingredient.name}: {qty} -> {new_qty}")

                # Check for Saborizante (7 -> 0.007)
                elif "sabor" in name and qty >= 1:
                     new_qty = qty / 1000
                     line.quantity = new_qty
                     line.save()
                     print(f"  -> Fixed {line.ingredient.name}: {qty} -> {new_qty}")
                     
                print(f"  - Line {line.ingredient.name}: {line.quantity}")

        # Trigger calc
        # Signal should handle it on save, but let's be sure
        bom.save()

    # 2. Fix Products
    products = Product.objects.filter(name__icontains="citrato")
    for p in products:
        print(f"Checking Product: {p.name}")
        if "100" in p.name and (p.net_weight >= 1 or p.net_weight == 0):
            p.net_weight = 0.1
            p.save()
            print(f"  -> Set Net Weight to 0.1")
        elif "200" in p.name and (p.net_weight >= 1 or p.net_weight == 0):
            p.net_weight = 0.2
            p.save()
            print(f"  -> Set Net Weight to 0.2")

    print("Done.")
