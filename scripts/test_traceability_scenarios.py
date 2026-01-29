
import os
import sys
import django
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction

# Setup Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from inventory.models import Ingredient, Product
from production.models import BillOfMaterial
from traceability.models import IngredientLot, ProductionBatch, BatchConsumption, StockAlert, TraceabilityConfig
from traceability.services import ProductionService, StockService

# -*- coding: utf-8 -*-
def run_scenarios():
    print("\n" + "="*70)
    print(" "*20 + "RUNNING TRACEABILITY SCENARIOS")
    print("="*70 + "\n")

    # Ensure config
    config = TraceabilityConfig.get_config()
    print(f"Config: Merma Thresh={config.waste_threshold_kg}kg, Low Stock={config.low_stock_threshold_kg}kg")

    # --- Scenario 1: FIFO Verification ---
    print("\nSCENARIO 1: FIFO Verification (Magnesio Complex)")
    
    # Debug: List all BOMs
    print("   Available BOMs in DB:")
    for b in BillOfMaterial.objects.all():
        print(f"   - '{b.name}' (ID: {b.id})")

    # Get BOM
    try:
        mag_bom = BillOfMaterial.objects.get(name__icontains='Magnesio Complex')
        print(f"   Found BOM: {mag_bom.name}")
    except BillOfMaterial.DoesNotExist:
        print("   ❌ CRITICAL: BOM 'Magnesio Complex' not found!")
        return
        
    mag_product = mag_bom.products.first() # Magnesio Complex
    
    # We need to produce enough to consume from multiple lots if possible.
    # Current stock in create_test_data:
    # Citrate: Lot 1 (25kg), Lot 2 (25kg). Recipe needs 0.45 kg per unit.
    # Maltodextrin: Lot 1 (50kg), Lot 2 (50kg). Recipe: 0.3 kg.
    
    # Let's produce 100 units. Total needed: 45kg Citrate, 30kg Malto.
    # This should consume Lot 1 entirely (25kg) and part of Lot 2 (20kg) for Citrate.
    
    qty_to_produce = Decimal('100.00')
    print(f"   Producing {qty_to_produce} units of {mag_product.name}...")
    
    try:
        batch = ProductionService.register_production(
            product=mag_product,
            bom=mag_bom,
            quantity_produced=qty_to_produce,
            internal_lot_code=f"BATCH-TEST-{date.today().strftime('%Y%m%d')}-01",
            user=None,
            notes="Automated Test Batch"
        )
        print(f"   Batch Produced: {batch.internal_lot_code}")
        
        # Verify Consumption
        print("   Verifying Consumption...")
        consumptions = batch.consumptions.all().select_related('ingredient', 'ingredient_lot')
        
        citrate_consumptions = [c for c in consumptions if "Citrato" in c.ingredient.name]
        
        # Sort by lot internal ID or date to verify order
        citrate_consumptions.sort(key=lambda x: x.ingredient_lot.internal_id)
        
        total_citrate = sum(c.quantity_consumed for c in citrate_consumptions)
        print(f"      Total Citrate Consumed: {total_citrate}kg (Expected: 45.0kg)")
        
        for c in citrate_consumptions:
            print(f"      - Lot {c.ingredient_lot.internal_id}: {c.quantity_consumed}kg (Waste: {c.is_waste})")
            
        # Assertion logic
        # Expecting first lot to be fully consumed (approx 25)
        # We can't strict assert IDs because they might vary if re-run, but we can check if multiple lots were used.
        if len(citrate_consumptions) > 1:
             print("      FIFO Validation: Multiple lots used (Oldest first expected) - OK")
        else:
             print("      FIFO Warning: Only one lot used (Check if lot size was sufficient)")

    except Exception as e:
        print(f"   Error in Scenario 1: {e}")


    # --- Scenario 2: Waste Logic ---
    print("\nSCENARIO 2: Waste (Merma) Logic")
    
    # Pick an ingredient and manually adjust a lot to be near waste threshold
    vit_c = Ingredient.objects.get(name='Vitamina C')
    
    # Create a small dummy lot
    small_lot = StockService.register_purchase(
        ingredient=vit_c,
        quantity=Decimal('0.150'), # 150g
        supplier_lot='WASTE-TEST-001',
        expiration_date=date.today() + timedelta(days=365)
    )
    print(f"   Created small lot {small_lot.internal_id} with 0.150kg")
    
    # Consume 0.060kg. Remaining 0.090kg. Threshold is 0.100kg.
    # Should trigger waste for the remaining 0.090kg.
    
    print("   Simulating direct consumption (via ProductionService internal logic mock or simple update)...")
    # We'll use the service method consume_ingredients_fifo directly to test logic
    try:
        consumptions = ProductionService.consume_ingredients_fifo(vit_c, Decimal('0.060'))
        
        found_waste = False
        for c in consumptions:
             if c['lot'].id == small_lot.id:
                 print(f"      Consumed: {c['quantity']}kg, Is Waste: {c['is_waste']}")
                 if c['is_waste']: 
                     found_waste = True 
                 # Check if there is a second entry for the waste
        
        # Re-fetch lot
        small_lot.refresh_from_db()
        print(f"   Lot status after: Active={small_lot.is_active}, Qty={small_lot.quantity_current}, Wasted={small_lot.is_wasted}")
        
        if small_lot.quantity_current == 0 and not small_lot.is_active:
            print("   Waste Logic: Lot emptied and deactivated. - OK")
        else:
            print("   Waste Logic: Lot not emptied properly.")

    except Exception as e:
        print(f"   Error in Scenario 2: {e}")


    # --- Scenario 3: Alerts ---
    print("\nSCENARIO 3: Stock Alerts")
    
    # Check for alerts generated by seed script or previous actions
    alerts = StockAlert.objects.filter(is_resolved=False)
    print(f"   Found {alerts.count()} active alerts:")
    for a in alerts:
        print(f"      - [{a.get_alert_type_display()}] {a.message}")
        
    if alerts.exists():
        print("   Stock Alerts: System is generating alerts. - OK")
    else:
        print("   Stock Alerts: No alerts found (Check thresholds).")

    print("\n" + "="*70)
    print(" "*25 + "SCENARIOS COMPLETED")
    print("="*70 + "\n")

if __name__ == '__main__':
    run_scenarios()
