from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Product, ProductionOrder

class CostService:
    @staticmethod
    def calculate_product_cost(product: Product) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculates the cost of a product based on its recipe.
        Returns: (total_cost, formula_cost, supply_cost)
        """
        total_formula_cost = Decimal('0')
        total_formula_weight = Decimal('0')
        total_supply_cost = Decimal('0')
        
        recipes = product.recipes.all()
        
        for recipe in recipes:
            ing = recipe.ingredient
            qty = recipe.quantity 
            
            # --- Formula Ingredients (Raw Materials) ---
            if ing.type == 'raw_material':
                # Determine Conversion Factor (Ingredient Unit -> Product Unit)
                factor = Decimal('1') 
                
                # Mass conversions
                if ing.unit == product.unit_measure:
                    factor = Decimal('1')
                elif ing.unit == 'kg' and product.unit_measure == 'g':
                    factor = Decimal('0.001') 
                elif ing.unit == 'g' and product.unit_measure == 'kg':
                    factor = Decimal('1000') 
                # Volume conversions
                elif ing.unit == 'l' and product.unit_measure == 'ml':
                    factor = Decimal('0.001')
                elif ing.unit == 'ml' and product.unit_measure == 'l':
                    factor = Decimal('1000')
                
                # Cost per product unit (e.g., cost per gram)
                unit_cost_aligned = Decimal(ing.cost_per_unit) * factor
                
                # Cost of this line item
                line_cost = qty * unit_cost_aligned
                total_formula_cost += line_cost
                
                # Weight of this line item (in Product Units)
                total_formula_weight += qty

            # --- Supplies (Packaging) ---
            elif ing.type == 'supply':
                # Cost is simply Qty * Unit Cost
                line_cost = qty * Decimal(ing.cost_per_unit)
                total_supply_cost += line_cost

        # --- Apply Scaling ---
        # Formula Cost = (Total Formula Cost / Total Formula Weight) * Product Net Weight
        final_formula_cost = Decimal('0')
        if total_formula_weight > 0:
            cost_per_unit_weight = total_formula_cost / total_formula_weight
            final_formula_cost = cost_per_unit_weight * Decimal(product.net_weight)
        
        total_product_cost = final_formula_cost + total_supply_cost
        
        return total_product_cost, final_formula_cost, total_supply_cost

    @staticmethod
    def update_product_cost(product: Product):
        """Calculates and saves the product cost."""
        total, formula, supplies = CostService.calculate_product_cost(product)
        product.cost_price = total
        product.save()
        return total, formula, supplies


class ProductionService:
    @staticmethod
    def process_production(product: Product, quantity: int) -> ProductionOrder:
        """
        Validates stock, deducts ingredients, increases product stock, and logs order.
        Raises ValidationError if insufficient stock.
        """
        recipes = product.recipes.all()
        if not recipes.exists():
            raise ValidationError(f"El producto {product.name} no tiene receta definida.")
            
        # 1. Validate Stock
        for recipe in recipes:
            required = recipe.quantity * quantity
            if recipe.ingredient.stock_quantity < required:
                raise ValidationError(
                    f"No hay suficiente {recipe.ingredient.name}. "
                    f"Requerido: {required}, Disponible: {recipe.ingredient.stock_quantity}"
                )
        
        # 2. Execute Transaction
        with transaction.atomic():
            # Deduct stock
            for recipe in recipes:
                required = recipe.quantity * quantity
                recipe.ingredient.stock_quantity -= required
                recipe.ingredient.save()
            
            # Add product stock
            product.stock_quantity += quantity
            product.save()
            
            # Log Order
            order = ProductionOrder.objects.create(
                user=product.user, # Assign same user as product
                product=product,
                quantity=quantity, 
                status='completed'
            )
            
        return order
