"""
Script para crear datos de prueba del sistema de trazabilidad.
Este script crea ingredientes, productos, BOMs y algunos lotes iniciales para testing.

Uso:
    python manage.py shell
    >>> exec(open('scripts/create_traceability_test_data.py').read())
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal
from datetime import date, timedelta

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User
from inventory.models import Ingredient, Product, Category
from production.models import BillOfMaterial, BomLine
from traceability.models import IngredientLot, TraceabilityConfig
from traceability.services import StockService


def create_test_data():
    print("\n" + "="*70)
    print(" "*20 + "CREANDO DATOS DE PRUEBA")
    print("="*70 + "\n")
    
    user = User.objects.first()
    if not user:
        print("❌ No hay usuarios. Crea uno primero con: python manage.py createsuperuser")
        return
    
    # 1. Crear configuración
    print("1️⃣ Creando configuración del sistema...")
    config = TraceabilityConfig.get_config()
    print(f"   ✓ Configuración lista: Merma={config.waste_threshold_kg}kg, Stock bajo={config.low_stock_threshold_kg}kg\n")
    
    # 2. Crear categoría
    print("2️⃣ Creando categoría...")
    category, _ = Category.objects.get_or_create(
        name="Suplementos",
        defaults={'user': user, 'description': 'Suplementos dietarios'}
    )
    print(f"   ✓ Categoría: {category.name}\n")
    
    # 3. Crear ingredientes
    print("3️⃣ Creando ingredientes...")
    ingredients_data = [
        {'name': 'Citrato de Magnesio', 'type': 'raw_material'},
        {'name': 'Maltodextrina', 'type': 'raw_material'},
        {'name': 'Vitamina C', 'type': 'raw_material'},
        {'name': 'Vitamina D3', 'type': 'raw_material'},
        {'name': 'Inositol', 'type': 'raw_material'},
    ]
    
    ingredients = {}
    for ing_data in ingredients_data:
        ing, created = Ingredient.objects.get_or_create(
            name=ing_data['name'],
            defaults={
                'user': user,
                'type': ing_data['type'],
                'unit': 'kg',
                'cost_per_unit': Decimal('10.00')
            }
        )
        ingredients[ing_data['name']] = ing
        status = "✓ Creado" if created else "○ Existe"
        print(f"   {status}: {ing.name}")
    
    print()
    
    # 4. Crear productos
    print("4️⃣ Creando productos...")
    products_data = [
        {'sku': 'MAG-001', 'name': 'Magnesio Complex', 'price': 2500.00},
        {'sku': 'VIT-001', 'name': 'Vitamina C Premium', 'price': 1800.00},
    ]
    
    products = {}
    for prod_data in products_data:
        prod, created = Product.objects.get_or_create(
            sku=prod_data['sku'],
            defaults={
                'user': user,
                'name': prod_data['name'],
                'category': category,
                'sale_price': Decimal(str(prod_data['price'])),
                'cost_price': Decimal(str(prod_data['price'] * 0.4)),
                'net_weight': Decimal('100.00'),
                'unit_measure': 'g'
            }
        )
        products[prod_data['name']] = prod
        status = "✓ Creado" if created else "○ Existe"
        print(f"   {status}: {prod.name} ({prod.sku})")
    
    print()
    
    # 5. Crear BOMs (recetas)
    print("5️⃣ Creando recetas (BOMs)...")
    
    # BOM para Magnesio Complex
    mag_bom, created = BillOfMaterial.objects.get_or_create(
        name='Fórmula Magnesio Complex',
        defaults={
            'user': user,
            'is_active': True,
            'quantity': Decimal('1.00')
        }
    )
    if created:
        mag_bom.products.add(products['Magnesio Complex'])
    print(f"   {'✓ Creada' if created else '○ Existe'}: {mag_bom.name}")
    
    # Ingredientes para Magnesio (gramos por kg de producto)
    mag_recipe = [
        (ingredients['Citrato de Magnesio'], 450),
        (ingredients['Maltodextrina'], 300),
        (ingredients['Vitamina C'], 100),
        (ingredients['Vitamina D3'], 0.5),
    ]
    
    for ingredient, grams in mag_recipe:
        line, created = BomLine.objects.get_or_create(
            bom=mag_bom,
            ingredient=ingredient,
            defaults={'quantity': Decimal(str(grams))}
        )
        if created:
            print(f"      + {grams}g de {ingredient.name}")
    
    # BOM para Vitamina C
    vitc_bom, created = BillOfMaterial.objects.get_or_create(
        name='Fórmula Vitamina C',
        defaults={
            'user': user,
            'is_active': True,
            'quantity': Decimal('1.00')
        }
    )
    if created:
        vitc_bom.products.add(products['Vitamina C Premium'])
    print(f"   {'✓ Creada' if created else '○ Existe'}: {vitc_bom.name}")
    
    vitc_recipe = [
        (ingredients['Vitamina C'], 800),
        (ingredients['Maltodextrina'], 200),
    ]
    
    for ingredient, grams in vitc_recipe:
        line, created = BomLine.objects.get_or_create(
            bom=vitc_bom,
            ingredient=ingredient,
            defaults={'quantity': Decimal(str(grams))}
        )
        if created:
            print(f"      + {grams}g de {ingredient.name}")
    
    print()
    
    # 6. Crear lotes de ingredientes (stock inicial)
    print("6️⃣ Creando stock inicial (lotes de ingredientes)...")
    
    lots_data = [
        {
            'ingredient': ingredients['Citrato de Magnesio'],
            'quantity': Decimal('25.000'),
            'supplier_lot': 'CIT-2025-001',
            'expiration': date.today() + timedelta(days=180)
        },
        {
            'ingredient': ingredients['Citrato de Magnesio'],
            'quantity': Decimal('25.000'),
            'supplier_lot': 'CIT-2025-002',
            'expiration': date.today() + timedelta(days=200)
        },
        {
            'ingredient': ingredients['Maltodextrina'],
            'quantity': Decimal('50.000'),
            'supplier_lot': 'MAL-2025-001',
            'expiration': date.today() + timedelta(days=365)
        },
        {
            'ingredient': ingredients['Maltodextrina'],
            'quantity': Decimal('50.000'),
            'supplier_lot': 'MAL-2025-002',
            'expiration': date.today() + timedelta(days=370)
        },
        {
            'ingredient': ingredients['Vitamina C'],
            'quantity': Decimal('10.000'),
            'supplier_lot': 'VITC-2025-001',
            'expiration': date.today() + timedelta(days=150)
        },
        {
            'ingredient': ingredients['Vitamina D3'],
            'quantity': Decimal('1.000'),
            'supplier_lot': 'VITD3-2025-001',
            'expiration': date.today() + timedelta(days=300)
        },
        {
            'ingredient': ingredients['Inositol'],
            'quantity': Decimal('15.000'),
            'supplier_lot': 'INO-2025-001',
            'expiration': date.today() + timedelta(days=250)
        },
    ]
    
    for lot_data in lots_data:
        try:
            lot = StockService.register_purchase(
                ingredient=lot_data['ingredient'],
                quantity=lot_data['quantity'],
                supplier_lot=lot_data['supplier_lot'],
                expiration_date=lot_data['expiration'],
                user=user
            )
            print(f"   ✓ {lot.internal_id}: {lot_data['quantity']}kg de {lot_data['ingredient'].name}")
        except Exception as e:
            # Probablemente ya existe
            print(f"   ○ Ya existe lote para {lot_data['ingredient'].name}: {lot_data['supplier_lot']}")
    
    print()
    
    # 7. Generar alertas iniciales
    print("7️⃣ Generando alertas iniciales...")
    StockService.check_and_create_alerts()
    print("   ✓ Alertas generadas\n")
    
    # Resumen final
    print("="*70)
    print(" "*25 + "✅ DATOS CREADOS")
    print("="*70)
    print(f"\n📦 Ingredientes: {Ingredient.objects.count()}")
    print(f"📊 Productos: {Product.objects.count()}")
    print(f"🧪 Recetas (BOMs): {BillOfMaterial.objects.count()}")
    print(f"🏷️  Lotes de stock: {IngredientLot.objects.filter(is_active=True).count()}")
    print(f"\n🌐 Accede al sistema en: http://localhost:8000/traceability/stock/")
    print()


if __name__ == '__main__':
    create_test_data()
