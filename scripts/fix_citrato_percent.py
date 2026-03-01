from production.models import BillOfMaterial, BomLine
from inventory.models import Product, Ingredient

def run():
    print("Converting Citrato Data back to %...")
    
    # Search by name/code seen in screenshot
    boms = BillOfMaterial.objects.filter(name__icontains="citra")
    for bom in boms:
        print(f"Checking BOM: {bom.name}")
        
        # Base Quantity remains 0.1 (Base of the batch)
        # But now line quantities for Raw Materials are PERCENTAGES.
        # Previously we set them to absolute kgs (e.g. 0.030 for 30g).
        # We need to convert 0.030 -> 30.0 (if Base is 0.1).
        # Ratio = Line / Base. % = Ratio * 100.
        
        for line in bom.lines.all():
            if line.ingredient and line.ingredient.user == bom.user: 
                # Ensure we only touch related ones
                
                if line.ingredient.type != 'supply':
                    # Raw Material -> Convert to %
                    current_qty = float(line.quantity)
                    
                    # If it looks like it was already converted (e.g. 30), skip?
                    # How to distinguish 0.03 (30g) from 0.03%?
                    # User likely has 0.03 now.
                    # If < 1, assumes it is absolute kg.
                    
                    if current_qty < 1:
                         # 0.030 / 0.1 * 100 = 0.3 * 100 = 30.
                         base = float(bom.quantity) if bom.quantity else 0.1
                         new_percent = (current_qty / base) * 100
                         
                         line.quantity = new_percent
                         line.save()
                         print(f"  -> Converted {line.ingredient.name}: {current_qty} -> {new_percent}%")
                     
                else:
                    print(f"  - Supply (Fixed): {line.ingredient.name}: {line.quantity}")
                    
        # Trigger calc
        bom.save()
        print("  -> Recalculated BOM Cost.")

    print("Done.")
