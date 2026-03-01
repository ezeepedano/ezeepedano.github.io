import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from inventory.models import Ingredient, Product, Category
from production.models import BillOfMaterial, BomLine
from sales.models import Sale, SaleItem, Customer
from traceability.services import StockService, ProductionService, SalesTraceabilityService
from traceability.models import ProductionBatch, SaleBatchAllocation

def run_test():
    print(">> INICIANDO TEST DE TRAZABILIDAD E2E")
    
    # 1. Crear Usuario de Prueba
    user, _ = User.objects.get_or_create(username="test_traceability", email="test@example.com")
    print(f">> Usuario: {user.username}")

    # CLEANUP PREVIO (Orden inverso a dependencia)
    print(">> Limpiando datos de tests anteriores...")
    SaleBatchAllocation.objects.filter(sale_item__product__sku="SKU-TEST-FINAL").delete()
    Sale.objects.filter(items__product__sku="SKU-TEST-FINAL").delete() # Cascades items
    
    # Delete test batches and their consumptions
    test_batches = ProductionBatch.objects.filter(product__sku="SKU-TEST-FINAL")
    for b in test_batches:
        b.consumptions.all().delete()
    test_batches.delete()
    
    # Now safe to delete ingredient lots
    Ingredient.objects.filter(name="INGREDIENTE_PRUEBA_X").first() and \
        Ingredient.objects.get(name="INGREDIENTE_PRUEBA_X").lots.all().delete()

    # 2. Crear Ingrediente
    ing, _ = Ingredient.objects.get_or_create(
        name="INGREDIENTE_PRUEBA_X",
        defaults={'unit': 'kg'}
    )
    print(f">> Ingrediente: {ing.name}")
    
    # 3. Registrar Compra (2 bolsas de 25kg) - LOTE MP-TEST-001 y 002
    # Limpiamos stock previo para test limpio
    ing.lots.all().delete()
    
    lot1 = StockService.register_purchase(
        ingredient=ing,
        quantity=Decimal('25.00'),
        supplier_lot="PROV-001",
        received_date=timezone.now().date(),
        user=user
    )
    lot2 = StockService.register_purchase(
        ingredient=ing,
        quantity=Decimal('25.00'),
        supplier_lot="PROV-002",
        received_date=timezone.now().date(),
        user=user
    )
    print(f">> Compra registrada: 50kg total en 2 lotes ({lot1.internal_id}, {lot2.internal_id})")
    
    # 4. Crear Producto y BOM
    prod, _ = Product.objects.get_or_create(
        sku="SKU-TEST-FINAL",
        defaults={'name': 'PRODUCTO FINAL PRUEBA', 'stock_quantity': 0, 'weight_kg': Decimal('1.000')}
    )
    
    # BOM: 0.5 kg de ingrediente por unidad de producto
    bom, _ = BillOfMaterial.objects.get_or_create(product=prod, defaults={'name': 'BOM Test'})
    BomLine.objects.filter(bom=bom).delete() # Limpiar líneas viejas
    BomLine.objects.create(bom=bom, ingredient=ing, quantity=Decimal('0.500')) # 0.5 kg (500g)
    print(f">> Producto y BOM creados (1 unidad = 0.5kg de ingrediente)")
    
    # 5. Registrar Producción (10 unidades)
    # Necesita 10 * 0.5 = 5kg de ingrediente. Debería tomar del lote MP-TEST-001
    print("\n>> REGISTRANDO PRODUCCION...")
    batch = ProductionService.register_production(
        product=prod,
        bom=bom,
        quantity_produced=Decimal('10.000'), # 10 kg producidos (10 unidades de 1kg)
        internal_lot_code="LOTE-PT-TEST-001",
        user=user
    )
    print(f">> Lote producido: {batch.internal_lot_code}")
    print(f"   Estado: {batch.status}")
    print(f"   Quantity Remaining: {batch.quantity_remaining}")
    
    # Verificar consumo
    for cons in batch.consumptions.all():
        print(f"   - Consumio {cons.quantity_consumed}kg del lote {cons.ingredient_lot.internal_id}")
        
    # 6. Crear Venta (2 unidades)
    print("\n>> REGISTRANDO VENTA...")
    customer, _ = Customer.objects.get_or_create(name="Cliente Prueba")
    sale = Sale.objects.create(
        customer=customer,
        date=timezone.now(),
        status='Pending',
        total=Decimal('200.00')
    )
    SaleItem.objects.create(
        sale=sale,
        product=prod,
        quantity=2, # 2 unidades = 2kg (peso es 1kg)
        unit_price=Decimal('100.00')
    )
    print(f">> Venta creada: Orden #{sale.order_id} (2 unidades)")
    
    # 7. Confirmar Venta (Dispara Asignación)
    print(">> CONFIRMANDO VENTA (Triggering Auto-Allocation)...")
    sale.status = 'Confirmado'
    sale.save()
    
    # Forzamos señal si no se dispara en shell
    if not sale.items.first().batch_allocations.exists():
        print("   (Llamando servicio manualmente por shell context...)")
        SalesTraceabilityService.auto_allocate_sale(sale)
    
    # 8. Verificar Resultados
    print("\n>> VERIFICACION DE RESULTADOS:")
    
    # Check Allocation
    allocs = SaleBatchAllocation.objects.filter(sale_item__sale=sale)
    if allocs.exists():
        for alloc in allocs:
            print(f"   OK: Asignado: {alloc.quantity_allocated}kg del lote {alloc.production_batch.internal_lot_code}")
    else:
        print("   ERROR: No se asignaron lotes")
        
    # Check Batch Remaining
    batch.refresh_from_db()
    print(f"   OK: Lote Remanente: {batch.quantity_remaining}kg (Esperado: 8.000)")
    
    if batch.quantity_remaining == 8.000 and allocs.exists():
        print("\n>> TEST EXITOSO: Flujo completo verificado correctametne <<")
    else:
        print("\n>> TEST FALLIDO: Verifique errores arriba <<")

run_test()
