import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient

def populate_codes():
    print("Populating codes for ingredients...")
    ingredients = Ingredient.objects.all().order_by('id')
    
    used_codes = set()
    
    # Pre-load existing codes if any (though we just added the column, they should be None)
    # But just in case
    for ing in ingredients:
        if ing.code:
            used_codes.add(ing.code)
            
    updated_count = 0
    
    for ing in ingredients:
        if ing.code:
            continue
            
        base_code = ing.name[:3].upper()
        # Clean special chars if needed, but assuming simple names for now
        # Ideally, remove spaces, special chars
        import re
        base_code = re.sub(r'[^A-Z0-9]', '', base_code)
        
        if len(base_code) < 3:
            base_code = (base_code + "XXX")[:3]
            
        candidate = base_code
        counter = 1
        
        while candidate in used_codes:
            # Conflict. Try appending number
            # e.g. MAG -> MA1 -> MA2...
            candidate = f"{base_code[:2]}{counter}"
            counter += 1
            if len(candidate) > 3: # Keep to 3 chars if possible? User said "MGS". 
                # Model max_length is 10. So it's fine to go longer.
                # But let's try to keep it short.
                pass
        
        ing.code = candidate
        ing.save()
        used_codes.add(candidate)
        updated_count += 1
        print(f"Updated {ing.name} -> {ing.code}")
        
    print(f"Finished. Updated {updated_count} ingredients.")

if __name__ == "__main__":
    populate_codes()
