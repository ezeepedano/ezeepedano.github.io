
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from inventory.models import Product
from django.contrib.auth.models import User

def seed_products():
    # SKUs provided by user
    skus = [
        "citramag100nrj", "citramag200nrj", "citramag500nrj", "citramag1000nrj", "citramag60caps",
        "treomag100nrj", "treomag200nrj", "treomag500nrj", "treomag1000nrj", "treomag60caps",
        "glicimag100nrj", "glicimag200nrj", "glicimag500nrj", "glicimag1000nrj", "glicimag60caps",
        "citrapot100nrj", "citrapot200nrj", "citrapot500nrj", "citrapot1000nrj", "citrapot60caps",
        "colage200nrj", "colage360nrj", "colage500nrj", "colage1000nrj", "colage60caps",
        "ascor100nrj", "ascor200nrj", "ascor500nrj", "ascor1000nrj", "ascor60caps",
        "multivital60caps",
        "magblend150",
        "potplus150",
        "ascorplus150",
        "colagebeauty360",
        "inosicare200",
        "termofit60caps",
        "multivitalfem60caps",
        "ciclofem60caps",
        "fastsun60caps",
        "termogen60caps",
        "triprotein900fruti",
        "triprotein900vaini",
        "wheyplatinum900vaini",
        "wheyplatinum900fruti",
        "wheyactive900vaini",
        "wheyactive900fruti",
        "crea150vaini",
        "crea300vaini",
        "crea500vaini",
        "crea1000vaini",
        "creaallinone220vaini",
        "creaallinone440vaini",
        "testobooster60caps",
        "testobooster180nrj",
        "BCAA200nrj",
        "maxenergy400nrj",
        "oxnitrico210nrj",
        "betaalanina300nrj",
        "betaalanina60caps",
        "colagesport380vaini",
        "spirulina60caps",
        "glucemic60caps",
        "mucolys60caps",
        "artrofix60caps",
        "descanso60caps",
        "novahair60caps",
        "inflavix60caps",
        "fertisol60caps"
    ]

    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("No superuser found. Assigning to None.")

    print(f"Checking {len(skus)} SKUs...")
    
    created_count = 0
    existing_count = 0
    
    for sku in skus:
        # Simple name formatter: caps first letter
        name = sku.upper() 
        
        product, created = Product.objects.get_or_create(
            sku=sku,
            defaults={
                'name': name,
                'user': user,
                'description': 'Imported from initial list',
                'net_weight': 100.00, # Default, user will edit
                'stock_quantity': 0
            }
        )
        
        if created:
            created_count += 1
            print(f"Created: {sku}")
        else:
            existing_count += 1
            # Optional: Update user if None
            if product.user is None and user:
                product.user = user
                product.save()

    print(f"\nSummary:")
    print(f"Created: {created_count}")
    print(f"Existing: {existing_count}")
    print(f"Total: {len(skus)}")

if __name__ == "__main__":
    seed_products()
