import pandas as pd
import django
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from inventory.models import Product, Ingredient
from production.models import BillOfMaterial, BomLine
from django.contrib.auth.models import User

def run():
    file_path = "Formulas_Organizadas_Final.xlsx"
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    print("Reading Excel file...")
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading excel: {e}")
        return
    
    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    print(f"Columns found: {df.columns.tolist()}")
    
    # Expected columns: sku, producto, ingrediente, porcentaje
    # Check if columns exist
    required_cols = ['sku', 'producto', 'ingrediente', 'porcentaje']
    for col in required_cols:
        if col not in df.columns:
            print(f"Error: Missing column '{col}'")
            return

    print(f"Loaded {len(df)} rows.")
    
    # Group by SKU
    grouped = df.groupby('sku')
    
    admin_user = User.objects.filter(is_superuser=True).first()
    
    for sku, group in grouped:
        product_name = group.iloc[0]['producto']
        sku = str(sku).strip()
        print(f"Processing {sku} - {product_name}...")
        
        # 1. Product
        product, created = Product.objects.get_or_create(
            sku=sku,
            defaults={'name': product_name, 'user': admin_user}
        )
        # Update name if it changed? Maybe better to keep existing if manually edited.
        # But user implies this excel is valid data. Let's update if different.
        if not created and product.name != product_name:
            product.name = product_name
            product.save()
            
        # 2. BOM
        # We assume base quantity 100 to match the percentage logic directly
        bom, _ = BillOfMaterial.objects.get_or_create(
            product=product,
            name="Fórmula Estándar",
            defaults={'quantity': 100.00, 'user': admin_user} 
        )
        
        # Clear existing lines to full reload
        bom.lines.all().delete()
        
        # 3. Lines
        for _, row in group.iterrows():
            ing_name = row['ingrediente']
            percentage = row['porcentaje']
            
            # Ingredient
            ingredient, _ = Ingredient.objects.get_or_create(
                name=ing_name,
                defaults={'user': admin_user, 'type': 'raw_material'}
            )
            
            # BomLine
            BomLine.objects.create(
                bom=bom,
                ingredient=ingredient,
                quantity=percentage
            )
            # print(f"  Added {percentage}% of {ing_name}")
            
    print("Import Complete!")

if __name__ == "__main__":
    run()
