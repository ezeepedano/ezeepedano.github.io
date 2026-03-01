import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient
from production.models import BillOfMaterial
from django.contrib.auth.models import User

def check_ownership():
    print("--- USERS ---")
    for u in User.objects.all():
        print(f"User ID: {u.id}, Username: {u.username}")

    print("\n--- INGREDIENTS OWNERSHIP ---")
    # Group by name to see duplicates side-by-side
    ingredients = Ingredient.objects.all().order_by('name')
    for ing in ingredients:
        user_str = f"User: {ing.user.username} (ID: {ing.user.id})" if ing.user else "User: None"
        print(f"ID: {ing.id}, Name: '{ing.name}', {user_str}")

    print("\n--- BOM OWNERSHIP ---")
    for bom in BillOfMaterial.objects.all():
        user_str = f"User: {bom.user.username} (ID: {bom.user.id})" if bom.user else "User: None"
        print(f"BOM ID: {bom.id}, Name: '{bom.name}', {user_str}")
        for line in bom.lines.all():
            ing = line.ingredient
            ing_user_str = f"User: {ing.user.username} (ID: {ing.user.id})" if ing.user else "User: None"
            print(f"  - Line Ing ID: {ing.id}, Name: '{ing.name}', Ing Owner: {ing_user_str}")

if __name__ == "__main__":
    check_ownership()
