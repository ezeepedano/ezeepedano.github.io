from django.test import TestCase
from decimal import Decimal
from .models import Product, Ingredient, Recipe
from .services import CostService, ProductionService
from django.core.exceptions import ValidationError

class CostServiceTests(TestCase):
    def setUp(self):
        # Create Ingredients
        self.flour = Ingredient.objects.create(
            name="Harina", 
            type='raw_material', 
            unit='kg', 
            cost_per_unit=Decimal('1000.00'), # $1000 per kg
            stock_quantity=100
        )
        self.sugar = Ingredient.objects.create(
            name="Azucar", 
            type='raw_material', 
            unit='kg', 
            cost_per_unit=Decimal('2000.00'), # $2000 per kg
            stock_quantity=50
        )
        self.bottle = Ingredient.objects.create(
            name="Botella", 
            type='supply', 
            unit='u', 
            cost_per_unit=Decimal('50.00'), # $50 per unit
            stock_quantity=200
        )
        
        # Create Product (Cake)
        self.cake = Product.objects.create(
            sku="CAKE001",
            name="Torta",
            net_weight=Decimal('500.00'), # 500g product
            unit_measure='g'
        )

    def test_cost_calculation_mass_conversion(self):
        # Recipe: 0.2kg Flour + 0.1kg Sugar (Total 300g input for 500g output? Scaling will happen)
        # Flour: $1000/kg * 0.2kg = $200
        # Sugar: $2000/kg * 0.1kg = $200
        # Total Formula Cost = $400
        # Total Formula Weight = 0.2kg + 0.1kg = 0.3kg = 300g (since product is in 'g', weight is sum of qtys converted? 
        # Wait, my service assumes qty is in Product's unit if unit mismatch? 
        # Let's review the service logic I wrote:
        # "if ing.unit == 'kg' and product.unit_measure == 'g': factor = 0.001"
        # "Weight of this line item... total_formula_weight += qty"
        # The Recipe quantity is defined in WHICH unit? 
        # The model says: "Cantidad requerida por unidad de producto". Usually this implies the Ingredient's unit.
        # BUT the logic in Service line 131 says: "Determine Conversion Factor (Ingredient Unit -> Product Unit)"
        # And line 155: "unit_cost_aligned = Decimal(ing.cost_per_unit) * factor"
        # And line 158: "line_cost = qty * unit_cost_aligned"
        
        # IF Recipe Qty is in INGREDIENT units (e.g. 0.2 kg), then:
        # Cost = 0.2 * 1000 = 200. Correct.
        # BUT logic line 168: "total_formula_weight += qty". 
        # If qty is 0.2 (kg), adding 0.2 to weight (which is used for scaling against Net Weight 500g) is wrong if the system expects grams.
        # Re-reading Service Logic:
        # It calculates `unit_cost_aligned` which seems to simply convert cost to match Product Unit?
        # IF Product is 'g', factor for 'kg' is 0.001.
        # unit_cost_aligned = 1000 * 0.001 = $1/g.
        # line_cost = qty * unit_cost_aligned.
        # If Qty is 0.2 (meaning 0.2 what?), if it's 0.2kg == 200g.
        # If we input 200 (g) into recipe: Cost = 200 * 1 = $200. Correct.
        # So Recipe Qty MUST be in Product Units (g) if Product is in g.
        
        # Let's verify standard ERP behavior. Usually Recipe Qty is in the Ingredient's Unit.
        # If my stored Qty is 0.2 (kg), then:
        # line_cost = 0.2 * 1 = 0.2 dollars. WRONG. Should be 200.
        
        # Looking at previous implementation (views.py before refactor):
        # It had generic "factor" logic but also confusion in comments.
        # "Total Formula Weight" logic implies it sums `qty`.
        # If I want to match a 500g Net Weight, the sum of ingredients should be ~500.
        # This implies inputs are in Grams (or Product Units).
        
        # So for this test, I will assume the Recipe Qty is meant to be in Product Units (g).
        # Recipe: 200g Flour, 100g Sugar.
        
        Recipe.objects.create(product=self.cake, ingredient=self.flour, quantity=Decimal('200'))
        Recipe.objects.create(product=self.cake, ingredient=self.sugar, quantity=Decimal('100'))
        
        total, formula, supplies = CostService.calculate_product_cost(self.cake)
        
        # Flour: 200g. Cost: $1000/kg = $1/g. -> $200.
        # Sugar: 100g. Cost: $2000/kg = $2/g. -> $200.
        # Formula Cost = $400.
        # Formula Weight = 300g.
        # Product Net Weight = 500g.
        # Scaling: (400 / 300) * 500 = 1.333 * 500 = 666.66
        
        expected_formula_cost = (Decimal('400') / Decimal('300')) * Decimal('500')
        self.assertAlmostEqual(formula, expected_formula_cost, places=2)
        self.assertAlmostEqual(total, expected_formula_cost, places=2)

    def test_cost_calculation_with_supplies(self):
        # Add Packaging using 'u' (units)
        Recipe.objects.create(product=self.cake, ingredient=self.flour, quantity=Decimal('500')) # 500g flour ($500)
        Recipe.objects.create(product=self.cake, ingredient=self.bottle, quantity=Decimal('2')) # 2 bottles ($100)
        
        # Formula: 500g Flour ($500). Weight 500. Net Weight 500. Scaling 1:1.
        # Supply: 2 * 50 = 100.
        # Total = 500 + 100 = 600.
        
        total, formula, supplies = CostService.calculate_product_cost(self.cake)
        
        self.assertEqual(formula, Decimal('500.00'))
        self.assertEqual(supplies, Decimal('100.00'))
        self.assertEqual(total, Decimal('600.00'))


class ProductionServiceTests(TestCase):
    def setUp(self):
        self.flour = Ingredient.objects.create(name="Harina", stock_quantity=1000, cost_per_unit=1) # 1000g
        self.product = Product.objects.create(sku="P1", name="Pan", stock_quantity=0)
        self.recipe = Recipe.objects.create(product=self.product, ingredient=self.flour, quantity=100) # 100g per unit

    def test_production_success(self):
        # Produce 5 units. Needs 500g flour. Stock 1000. OK.
        order = ProductionService.process_production(self.product, 5)
        
        self.product.refresh_from_db()
        self.flour.refresh_from_db()
        
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(self.flour.stock_quantity, 500)
        self.assertEqual(order.quantity, 5)

    def test_production_insufficient_stock(self):
        # Produce 20 units. Needs 2000g flour. Stock 1000. FAIL.
        with self.assertRaises(ValidationError):
            ProductionService.process_production(self.product, 20)
            
        self.product.refresh_from_db()
        self.flour.refresh_from_db()
        
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertEqual(self.flour.stock_quantity, 1000)
