import os
import sys
import django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from production.models import BillOfMaterial

def analyze_duplicates():
    # Helper to create a unique hash/signature for a BOM
    import hashlib
    
    signatures = {} # hash -> list of boms
    
    for bom in BillOfMaterial.objects.all():
        # Sort lines to ensure signature is consistent
        lines = sorted(list(bom.lines.all()), key=lambda l: l.ingredient.id)
        sig_str = ""
        for line in lines:
            sig_str += f"{line.ingredient.id}:{float(line.quantity)}|"
            
        if not sig_str:
            continue
            
        if sig_str not in signatures:
            signatures[sig_str] = []
        signatures[sig_str].append(bom)
        
    print(f"Found {len(signatures)} unique formulas across {BillOfMaterial.objects.count()} BOMs.")
    
    dupe_count = 0
    for sig, boms in signatures.items():
        if len(boms) > 1:
            dupe_count += 1
            print(f"\nFormula Signature: {sig[:30]}... (Shared by {len(boms)} products)")
            for b in boms:
                print(f"  - BOM ID {b.id}: {b.product.name} ({b.product.sku})")

analyze_duplicates()
