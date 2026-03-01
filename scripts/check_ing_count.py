import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient

def check_ingredients():
    count = Ingredient.objects.count()
    print(f"Ingredient count: {count}")
    if count > 0:
        print("Existing ingredients found:")
        for ing in Ingredient.objects.all()[:5]:
            print(f"- {ing.name} (ID: {ing.id})")

if __name__ == "__main__":
    check_ingredients()
