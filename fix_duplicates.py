import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.db import transaction
from sales.models import Customer, Sale
from django.contrib.auth.models import User

def fix_duplicates():
    # Iterate all users or specific user
    users = User.objects.all()
    
    for user in users:
        print(f"Processing user {user.username} (ID: {user.id})...")
        
        # Get all customers for user
        customers = Customer.objects.filter(user=user)
        
        legacy_candidates = []
        new_style_map = {} # Map of hash -> Customer (New Style)
        
        # classify
        for c in customers:
             # Check if key starts with "user_id_"
             prefix = f"{user.id}_"
             if c.dedup_key.startswith(prefix):
                 # This is likely a NEW style key
                 # The "original hash" is the part after prefix
                 original_hash = c.dedup_key[len(prefix):]
                 new_style_map[original_hash] = c
             else:
                 # Assume legacy
                 legacy_candidates.append(c)
                 
        print(f"  Found {len(legacy_candidates)} legacy candidates and {len(new_style_map)} new style records.")
        
        duplicates_found = 0
        with transaction.atomic():
            for legacy in legacy_candidates:
                # The legacy key IS the original hash (usually)
                # Let's verify if a corresponding NEW record exists
                legacy_hash = legacy.dedup_key
                
                if legacy_hash in new_style_map:
                    target = new_style_map[legacy_hash]
                    # DUPLICATE FOUND
                    print(f"  Merging Legacy {legacy.name} (ID: {legacy.id}) -> New {target.name} (ID: {target.id})")
                    
                    # Move Sales
                    sales = Sale.objects.filter(customer=legacy)
                    count = sales.count()
                    sales.update(customer=target)
                    print(f"    Moved {count} sales.")
                    
                    # Delete Legacy
                    legacy.delete()
                    duplicates_found += 1
        
        print(f"  Merged {duplicates_found} duplicates for user {user.username}.")

if __name__ == '__main__':
    fix_duplicates()
