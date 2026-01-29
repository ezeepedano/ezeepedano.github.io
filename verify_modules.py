import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from django.contrib.auth.models import User
from inventory.models import Product, Ingredient, Batch, SupplierPrice
from production.models import BillOfMaterial, BomLine, ProductionOrder
from logistics.models import Vehicle, DeliveryRoute
from sales.models import Sale, Customer
from finance.models import Provider

def test_flow():
    print("--- Starting Verification Flow ---")
    
    # 1. Setup User and Basic Data
    user, _ = User.objects.get_or_create(username="testadmin")
    
    # 2. PROVEEDORES & PRECIOS (Supplier Pricing)
    provider, _ = Provider.objects.get_or_create(name="Proveedor Test", user=user)
    ingred, _ = Ingredient.objects.get_or_create(name="Harina", user=user)
    price, _ = SupplierPrice.objects.get_or_create(provider=provider, ingredient=ingred, defaults={'price': 500})
    print(f"[OK] Supplier Price Set: {price}")

    # 3. PRODUCTION (BOM)
    product, _ = Product.objects.get_or_create(name="Pan Casero", sku="PAN001", user=user)
    bom, _ = BillOfMaterial.objects.get_or_create(product=product, name="Receta Base", user=user)
    
    # Add ingredient to BOM
    if not bom.lines.exists():
        BomLine.objects.create(bom=bom, ingredient=ingred, quantity=0.5)
    print(f"[OK] BOM Created: {bom}")

    # 4. BATCH (Lote y Vencimiento)
    batch, _ = Batch.objects.get_or_create(
        number="LOTE-001", 
        ingredient=ingred, 
        defaults={'quantity': 100, 'user': user}
    )
    print(f"[OK] Batch Created: {batch}")

    # 5. PRODUCTION ORDER (MRP)
    # Simulate Logic: Use BOM to Produce
    po = ProductionOrder.objects.create(
        product=product,
        bom=bom,
        quantity_to_produce=10,
        user=user,
        status='DRAFT'
    )
    print(f"[OK] Production Order Created: {po}")

    # 6. LOGISTICS
    vehicle, _ = Vehicle.objects.get_or_create(name="Camion 1", plate="AA123BB", user=user)
    route = DeliveryRoute.objects.create(vehicle=vehicle, date="2024-01-01", user=user)
    print(f"[OK] Delivery Route Created: {route}")
    
    print("--- Verification Complete ---")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        print(f"[ERROR] {e}")
