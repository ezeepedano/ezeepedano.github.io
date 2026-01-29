import os
import sys
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from inventory.models import Product, Ingredient
from production.models import BillOfMaterial, BomLine
from django.db.models import Sum

def verify_integrity():
    print("--- Starting Comprehensive Formula Check ---")
    
    total_boms = BillOfMaterial.objects.count()
    print(f"Total Formulas: {total_boms}")
    
    # 1. Check Totals (Should sum to ~100)
    print("\n[1] Checking Percentage Sums...")
    issues = []
    
    for bom in BillOfMaterial.objects.all():
        total_qty = bom.lines.aggregate(Sum('quantity'))['quantity__sum'] or 0
        if abs(total_qty - 100) > 0.01: # Check for floating point drift
            issues.append(f"{bom.product.sku}: Sums to {total_qty}% (Expected 100%)")
            
    if not issues:
        print("[OK] All 70 formulas sum exactly to 100%.")
    else:
        print(f"[WARNING] Found {len(issues)} formulas with irregular sums:")
        for i in issues[:5]: 
            print("  - " + i)
            
    # 2. Spot Check: Capsule vs Powder
    # "Polvos: Llevan Saborizante. Cápsulas: NO llevan saborizante"
    print("\n[2] Checking Logic (Capsules vs Powders)...")
    
    # Check a Powder: citramag100nrj
    p_powder = Product.objects.filter(sku='citramag100nrj').first()
    if p_powder:
        has_flavor = p_powder.boms.first().lines.filter(ingredient__name__icontains="Saborizante").exists()
        print(f"  - Powder (citramag100): has Saborizante? {'YES [OK]' if has_flavor else 'NO [Check!]'} ({p_powder.boms.first().lines.filter(ingredient__name__icontains='Saborizante').first()})")

    # Check a Capsule: citramag60caps
    p_cap = Product.objects.filter(sku='citramag60caps').first()
    if p_cap:
        bom_cap = p_cap.boms.first()
        if bom_cap:
            has_flavor = bom_cap.lines.filter(ingredient__name__icontains="Saborizante").exists()
            malto_line = bom_cap.lines.filter(ingredient__name__icontains="Maltodextrina").first()
            malto_qty = malto_line.quantity if malto_line else 0
            
            print(f"  - Capsule (citramag60caps): has Saborizante? {'YES [Unexpected]' if has_flavor else 'NO [OK]'}")
            print(f"  - Capsule Maltodextrina Content: {malto_qty}%")
    
    print("\n--- Check Complete ---")

if __name__ == "__main__":
    verify_integrity()
