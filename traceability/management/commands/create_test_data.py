"""
Management command para crear datos de prueba del sistema de trazabilidad.
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth.models import User

from inventory.models import Ingredient, Product, Category
from production.models import BillOfMaterial, BomLine
from traceability.models import IngredientLot, TraceabilityConfig
from traceability.services import StockService


class Command(BaseCommand):
    help = 'Crea datos de prueba para el sistema de trazabilidad'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('  CREANDO DATOS DE PRUEBA'))
        self.stdout.write('='*70 + '\n')
        
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No hay usuarios. Crea uno primero.'))
            return
        
        # 1. Configuración
        self.stdout.write('1. Creando configuración...')
        config = TraceabilityConfig.get_config()
        self.stdout.write(self.style.SUCCESS(f'   OK - Merma={config.waste_threshold_kg}kg\n'))
        
        # 2. Categoría
        self.stdout.write('2. Creando categoría...')
        category, _ = Category.objects.get_or_create(
            name="Suplementos",
            defaults={'user': user}
        )
        self.stdout.write(self.style.SUCCESS(f'   OK - {category.name}\n'))
        
        # 3. Ingredientes
        self.stdout.write('3. Creando ingredientes...')
        ingredients = {}
        for name in ['Citrato de Magnesio', 'Maltodextrina', 'Vitamina C', 'Vitamina D3', 'Inositol']:
            ing, created = Ingredient.objects.get_or_create(
                name=name,
                defaults={'user': user, 'type': 'raw_material', 'unit': 'kg'}
            )
            ingredients[name] = ing
            self.stdout.write(f'   {"Creado" if created else "Existe"}: {name}')
        self.stdout.write('')
        
        # 4. Productos
        self.stdout.write('4. Creando productos...')
        products = {}
        prods_data = [
            ('MAG-001', 'Magnesio Complex', 2500),
            ('VIT-001', 'Vitamina C Premium', 1800),
        ]
        for sku, name, price in prods_data:
            prod, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'user': user, 'name': name, 'category': category,
                    'sale_price': Decimal(str(price))
                }
            )
            products[name] = prod
            self.stdout.write(f'   {"Creado" if created else "Existe"}: {name}')
        self.stdout.write('')
        
        # 5. BOMs
        self.stdout.write('5. Creando recetas (BOMs)...')
        
        mag_bom, _ = BillOfMaterial.objects.get_or_create(
            name='Formula Magnesio Complex',
            defaults={'user': user, 'is_active': True}
        )
        mag_bom.products.add(products['Magnesio Complex'])
        
        for ing_name, grams in [('Citrato de Magnesio', 450), ('Maltodextrina', 300), 
                                ('Vitamina C', 100), ('Vitamina D3', 0.5)]:
            BomLine.objects.get_or_create(
                bom=mag_bom, ingredient=ingredients[ing_name],
                defaults={'quantity': Decimal(str(grams))}
            )
        self.stdout.write(f'   OK - {mag_bom.name}')
        
        vitc_bom, _ = BillOfMaterial.objects.get_or_create(
            name='Formula Vitamina C',
            defaults={'user': user, 'is_active': True}
        )
        vitc_bom.products.add(products['Vitamina C Premium'])
        
        for ing_name, grams in [('Vitamina C', 800), ('Maltodextrina', 200)]:
            BomLine.objects.get_or_create(
                bom=vitc_bom, ingredient=ingredients[ing_name],
                defaults={'quantity': Decimal(str(grams))}
            )
        self.stdout.write(f'   OK - {vitc_bom.name}\n')
        
        # 6. Stock inicial
        self.stdout.write('6. Creando stock inicial...')
        lots_data = [
            (ingredients['Citrato de Magnesio'], 25, 'CIT-001', 180),
            (ingredients['Citrato de Magnesio'], 25, 'CIT-002', 200),
            (ingredients['Maltodextrina'], 50, 'MAL-001', 365),
            (ingredients['Maltodextrina'], 50, 'MAL-002', 370),
            (ingredients['Vitamina C'], 10, 'VITC-001', 150),
            (ingredients['Vitamina D3'], 1, 'VITD3-001', 300),
        ]
        
        for ingredient, qty, lot, days in lots_data:
            # Verificar si ya existe
            if IngredientLot.objects.filter(supplier_lot=lot).exists():
                self.stdout.write(f'   Existe: {lot}')
                continue
                
            try:
                lot_obj = StockService.register_purchase(
                    ingredient=ingredient,
                    quantity=Decimal(str(qty)),
                    supplier_lot=lot,
                    expiration_date=date.today() + timedelta(days=days),
                    user=user
                )
                self.stdout.write(f'   OK - {lot_obj.internal_id}: {qty}kg de {ingredient.name}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'   Error: {e}'))
        
        self.stdout.write('')
        
        # 7. Alertas
        self.stdout.write('7. Generando alertas...')
        StockService.check_and_create_alerts()
        self.stdout.write(self.style.SUCCESS('   OK\n'))
        
        # Resumen
        self.stdout.write('='*70)
        self.stdout.write(self.style.SUCCESS('  DATOS CREADOS'))
        self.stdout.write('='*70)
        self.stdout.write(f'\nIngredientes: {Ingredient.objects.count()}')
        self.stdout.write(f'Productos: {Product.objects.count()}')
        self.stdout.write(f'BOMs: {BillOfMaterial.objects.count()}')
        self.stdout.write(f'Lotes: {IngredientLot.objects.filter(is_active=True).count()}')
        self.stdout.write('\nURL: http://localhost:8000/traceability/stock/')
        self.stdout.write('')
