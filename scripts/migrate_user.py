import os
import django
import sys

# Setup Django environment to allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction

def migrate_user_data():
    User = get_user_model()
    
    print("Starting migration from 'user' to 'INSAF'...")
    
    # 1. Get old user
    try:
        old_user = User.objects.get(username='user')
        print(f"Found old user: {old_user.username} (ID: {old_user.id})")
    except User.DoesNotExist:
        print("ERROR: User 'user' does not exist. Aborting migration.")
        return

    # 2. Get or Create new user
    new_user, created = User.objects.get_or_create(username='INSAF')
    if created:
        print("Created new user: INSAF")
    else:
        print("Found existing user: INSAF")
        
    # 3. Set password
    print("Setting password for INSAF...")
    new_user.set_password('INSAFadmin2026')
    new_user.is_staff = old_user.is_staff # Copy permissions
    new_user.is_superuser = old_user.is_superuser
    new_user.save()
    print("Password updated.")

    # 4. Migrate data
    print("\nScanning models for relationships...")
    
    with transaction.atomic():
        # Iterate over all installed models
        for model in apps.get_models():
            # Skip the User model itself
            if model == User:
                continue
                
            # Inspect fields
            for field in model._meta.get_fields():
                # specific check for ForeignKeys or OneToOneFields pointing to User
                # We check `related_model` matches User
                if field.is_relation and field.related_model == User:
                    # Ensure it's a concrete field on this model (not a reverse relation from another model)
                    if field.concrete and (field.many_to_one or field.one_to_one):
                        field_name = field.name
                        
                        # Check if there are any records to update
                        filter_kwargs = {field_name: old_user}
                        qs = model.objects.filter(**filter_kwargs)
                        count = qs.count()
                        
                        if count > 0:
                            print(f"Migrating {count} records in {model._meta.label} (Field: {field_name})...")
                            # Perform update
                            update_kwargs = {field_name: new_user}
                            qs.update(**update_kwargs)
        
        print("\nMigration of ForeignKeys completed successfully.")
        
        # Optional: Transfer Groups and Permissions (Many-to-Many)
        print("Transferring groups and permissions...")
        new_user.groups.set(old_user.groups.all())
        new_user.user_permissions.set(old_user.user_permissions.all())
        new_user.save()
        
    print("\n------------------------------------------------")
    print("SUCCESS: usage of 'user' has been transferred to 'INSAF'.")
    print("NOTE: 'user' still exists but should have no related objects (except M2Ms which were copied).")

if __name__ == '__main__':
    migrate_user_data()
