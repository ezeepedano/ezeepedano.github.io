
from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from inventory.models import Product, Ingredient, Recipe
from sales.models import Sale, SaleItem
from inventory.services_intelligence import StockIntelligenceService

class StockIntelligenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testadmin', password='password')
        
        # 1. Create Raw Material (Magnesium Citrate)
        self.magnesium = Ingredient.objects.create(
            user=self.user,
            name='Citrato de Magnesio',
            type='raw_material',
            stock_quantity=Decimal('5000.00'), # 5kg Stock
            unit='g'
        )
        
        # 2. Create Product (Magnesium Supplement 1kg)
        self.product = Product.objects.create(
            user=self.user,
            name='Magnesio 1kg',
            sku='MG1KG'
        )
        
        # 3. Create Recipe (Each product uses 500g of Magnesium - just an example)
        Recipe.objects.create(
            user=self.user,
            product=self.product,
            ingredient=self.magnesium,
            quantity=Decimal('500.00') # 500g per unit
        )

    def test_forecast_calculation(self):
        """
        Scenario:
        - 5000g Stock.
        - Recipe: 500g per unit.
        - Sales: 10 units in last 10 days = 1 unit/day.
        - Daily Usage: 1 * 500g = 500g/day.
        - Runway: 5000 / 500 = 10 days.
        """
        
        # Create Sales
        # We need average of 30 days.
        # If I create 10 sales of 1 unit in the last 30 days...
        # Total Units = 10.
        # Total Usage = 10 * 500 = 5000g.
        # Days History = 30.
        # Daily Usage = 5000 / 30 = 166.66g/day.
        
        # Let's make it simpler for exact math.
        # Let's say we sold 30 units in 30 days. (1 per day)
        
        today = timezone.now()
        
        for i in range(30):
            sale = Sale.objects.create(
                user=self.user,
                date=today - timedelta(days=i),
                total=100,
                status='completed'
            )
            SaleItem.objects.create(
                sale=sale,
                product=self.product,
                quantity=1
            )
            
        service = StockIntelligenceService(days_history=30)
        result = service.calculate_ingredient_runway(self.magnesium)
        
        print(f"DEBUG: Daily Usage: {result['daily_usage']}")
        print(f"DEBUG: Runway Days: {result['runway_days']}")
        
        # Daily Usage shoud be: (30 units * 500g) / 30 days = 500g/day.
        self.assertAlmostEqual(result['daily_usage'], Decimal('500.00'), places=2)
        
        # Runway: 5000g stock / 500g/day = 10 days.
        # Use delta for float comparison
        self.assertAlmostEqual(result['runway_days'], 10.0, delta=0.1)
        
        # Status
        self.assertEqual(result['status'], 'WARNING')

    def test_no_sales_forecast(self):
        service = StockIntelligenceService(days_history=30)
        result = service.calculate_ingredient_runway(self.magnesium)
        
        self.assertEqual(result['daily_usage'], Decimal('0.00'))
        self.assertEqual(result['runway_days'], 9999)
        self.assertEqual(result['status'], 'SAFE')
