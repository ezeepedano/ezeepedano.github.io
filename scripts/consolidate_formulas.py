import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from production.models import BillOfMaterial

def consolidate():
    print("--- Consolidating Formulas ---")
    
    # 1. Populate M2M from FK
    print("Migrating FK -> M2M ...")
    for bom in BillOfMaterial.objects.all():
        if bom.product:
            bom.products.add(bom.product)
    
    # 2. Logic to Find Duplicates
    signatures = {}
    
    all_boms = list(BillOfMaterial.objects.all())
    print(f"Analyzing {len(all_boms)} BOMs...")
    
    for bom in all_boms:
        # Signature logic
        lines = sorted(list(bom.lines.all()), key=lambda l: l.ingredient.id)
        sig_str = ""
        for line in lines:
            sig_str += f"{line.ingredient.id}:{float(line.quantity)}|"
            
        if not sig_str:
            print(f"Skipping empty BOM {bom.id}")
            continue
            
        if sig_str not in signatures:
            signatures[sig_str] = []
        signatures[sig_str].append(bom)
        
    # 3. Merge
    for sig, boms in signatures.items():
        if len(boms) > 1:
            # We have duplicates!
            master = boms[0]
            duplicates = boms[1:]
            
            print(f"\nMerging {len(duplicates)} duplicate BOMs into Master ID {master.id} ({master.name})")
            
            # Update Master Name to be generic if it's specific
            # E.g. "Citrato De Magnesio 100 Gramos" -> "Fórmula Citrato De Magnesio"
            # Simple heuristic: Split by keywords like "100", "Gramos", "Caps" and take prefix?
            # Or just take the product name without the size.
            # Using the first product's name
            base_name = master.product.name if master.product else "Formula"
            # Try to strip size info (very naive)
            import re
            generic_name = re.sub(r'\d+\s*(Gramos|Caps|mg|g|ml)', '', base_name, flags=re.IGNORECASE).strip()
            generic_name = f"Fórmula {generic_name}"
            
            master.name = generic_name
            master.save()
            print(f"  Renamed Master to: {master.name}")
            
            # Move Products
            for dup in duplicates:
                for prod in dup.products.all():
                    print(f"  Moving product {prod.name} to Master BOM")
                    master.products.add(prod)
                
                # Delete Duplicate
                print(f"  Deleting duplicate BOM ID {dup.id}")
                dup.delete()
                
    print("--- Consolidation Complete ---")
    print(f"Remaining BOMs: {BillOfMaterial.objects.count()}")

if __name__ == "__main__":
    consolidate()
