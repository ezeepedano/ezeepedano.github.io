
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Ingredient, Recipe, Product
from sales.models import Sale, SaleItem

class StockIntelligenceService:
    def __init__(self, days_history=30):
        self.days_history = days_history
        self.today = timezone.now()
        self.start_date = self.today - timedelta(days=days_history)

    def calculate_ingredient_runway(self, ingredient):
        """
        Calculates how many days an ingredient will last based on recent sales.
        Returns:
            - daily_usage (Decimal): Average quantity used per day.
            - runway_days (float): Days until stock runs out. (9999 if infinite/no usage)
            - project_depletion_date (Date): Estimated date of 0 stock.
        """
        # 1. Find all products that use this ingredient
        recipes = Recipe.objects.filter(ingredient=ingredient)
        
        total_usage_in_period = Decimal('0.00')
        
        for recipe in recipes:
            product = recipe.product
            quantity_per_unit = recipe.quantity
            
            # 2. Get sales volume for this product in the period
            # We filter by Sale date and ensure status is valid/completed
            sold_quantity = SaleItem.objects.filter(
                sale__date__gte=self.start_date,
                sale__status__in=['paid', 'completed', 'delivered', 'sent'],
                product=product
            ).aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
            
            # 3. Calculate total ingredient usage
            total_usage_in_period += (Decimal(sold_quantity) * quantity_per_unit)
            
        # 4. Calculate Daily Average
        if total_usage_in_period <= 0:
            return {
                'daily_usage': Decimal('0.00'),
                'runway_days': 9999, # Infinite
                'depletion_date': None,
                'status': 'SAFE'
            }
            
        daily_usage = total_usage_in_period / Decimal(self.days_history)
        
        # 5. Calculate Runway
        current_stock = ingredient.stock_quantity
        
        if daily_usage > 0:
            runway_days = float(current_stock) / float(daily_usage)
            depletion_date = self.today + timedelta(days=runway_days)
        else:
            runway_days = 9999
            depletion_date = None
            
        # 6. Determine Status
        status = 'SAFE'
        if runway_days < 7:
            status = 'CRITICAL'
        elif runway_days < 30:
            status = 'WARNING'
            
        return {
            'daily_usage': daily_usage,
            'runway_days': runway_days,
            'depletion_date': depletion_date,
            'status': status
        }

    def get_all_ingredients_forecast(self):
        """
        Returns a list of all raw materials with their forecast data, sorted by criticality.
        """
        ingredients = Ingredient.objects.filter(type='raw_material')
        results = []
        
        for ing in ingredients:
            data = self.calculate_ingredient_runway(ing)
            data['ingredient'] = ing
            results.append(data)
            
        # Sort by runway_days ascending (lowest runway first)
        results.sort(key=lambda x: x['runway_days'])
        
        return results
