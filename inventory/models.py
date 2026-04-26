"""
Inventory Models Module

Defines all inventory-related models including products, ingredients,
categories, recipes, production orders, batches, and supplier pricing.

Models:
    - Category: Product categorization
    - Product: Final sellable products with stock tracking
    - Ingredient: Raw materials and supplies with lot tracking
    - Recipe: Product formulas (Bill of Materials)
    - ProductionOrder: Manufacturing orders (legacy/simple)
    - Batch: Lot tracking for ingredients and products
    - SupplierPrice: Multi-supplier pricing management

Author: ERP Development Team
Created: 2025-01-01
Updated: 2026-02-04
"""

from typing import Optional
from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    """
    Product Category Model
    
    Organizes products into hierarchical categories for better management
    and reporting. Used for inventory organization and sales analysis.
    
    Attributes:
        user: Owner/creator of the category (optional, multi-tenant ready)
        name: Category name (e.g., "Supplements", "Vitamins")
        description: Detailed category description (optional)
    
    Examples:
        >>> category = Category.objects.create(
        ...     name="Dietary Supplements",
        ...     description="Health and wellness supplements"
        ... )
        >>> str(category)
        'Dietary Supplements'
    
    Meta:
        verbose_name: Category
        verbose_name_plural: Categories
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Category owner/creator"
    )
    name = models.CharField(
        max_length=100,
        help_text="Category name"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed category description"
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self) -> str:
        """Return category name as string representation."""
        return self.name

class Product(models.Model):
    """
    Final Product Model
    
    Represents sellable finished products in inventory. Each product has
    associated costs, pricing, stock levels, and optional Bill of Materials (BOM)
    for production tracking.
    
    Attributes:
        user: Product owner (multi-tenant support)
        sku: Stock Keeping Unit - unique product identifier
        name: Product name/description
        description: Detailed product description
        category: Product category for organization
        cost_price: Production/acquisition cost per unit
        sale_price: Selling price per unit
        net_weight: Net content weight per unit (for recipe calculations)
        unit_measure: Measurement unit (g, kg, ml, l)
        stock_quantity: Current available stock (units)
        weight_kg: Weight per unit in kg (for logistics/shipping)
        created_at: Timestamp when product was created
        updated_at: Timestamp of last modification
    
    Related Models:
        - Category: via category FK
        - Recipe: via recipes reverse relation
        - BillOfMaterial: via production.BillOfMaterial
        - Sale: via sales.SaleItem
    
    Examples:
        >>> product = Product.objects.create(
        ...     sku="MAG500",
        ...     name="Magnesium Citrate 500g",
        ...     cost_price=Decimal('1250.00'),
        ...     sale_price=Decimal('2500.00'),
        ...     stock_quantity=100,
        ...     net_weight=Decimal('500.00'),
        ...     unit_measure='g',
        ...     weight_kg=Decimal('0.550')
        ... )
        >>> str(product)
        'MAG500 - Magnesium Citrate 500g'
    
    Meta:
        unique_together: (user, sku) to prevent SKU conflicts per user
    """
    
    UNIT_CHOICES = [
        ('g',  'Gramos'),
        ('kg', 'Kilogramos'),
        ('ml', 'Mililitros'),
        ('l',  'Litros'),
        ('u',  'Unidades'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Product owner/creator"
    )
    sku = models.CharField(
        max_length=50,
        help_text="Stock Keeping Unit - unique product code"
    )
    name = models.CharField(
        max_length=200,
        help_text="Product name"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed product description"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Product category"
    )
    
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Production/acquisition cost per unit"
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Selling price per unit"
    )
    
    net_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="Net content weight per unit (for recipe calculations)"
    )
    unit_measure = models.CharField(
        max_length=10,
        choices=UNIT_CHOICES,
        default='g',
        help_text="Unit of measurement"
    )

    stock_quantity = models.IntegerField(
        default=0,
        help_text="Current stock quantity (units)"
    )
    min_stock = models.IntegerField(
        default=10,
        help_text="Minimum stock threshold for low-stock alerts. "
                  "Customizable per product (was hardcoded to 10 before)."
    )

    # Traceability: weight per unit in kg for logistics
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1.00,
        help_text="Weight per unit in kg (e.g., 0.500 for 500g bottle)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    
    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        unique_together = ['user', 'sku']
        ordering = ['sku', 'name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['stock_quantity']),
        ]

    def __str__(self) -> str:
        """Return SKU and name as string representation."""
        return f"{self.sku} - {self.name}"
    
    @property
    def profit_margin(self) -> float:
        """
        Calculate profit margin percentage.
        
        Returns:
            Profit margin as percentage (0-100)
        
        Example:
            >>> product.cost_price = 1000
            >>> product.sale_price = 2000
            >>> product.profit_margin
            50.0
        """
        if self.cost_price == 0:
            return 0.0
        return float((self.sale_price - self.cost_price) / self.cost_price * 100)
    
    @property
    def is_low_stock(self) -> bool:
        """
        Check if product stock is at or below the per-product threshold.

        Returns:
            True when ``stock_quantity <= min_stock``; False otherwise.
            Defaults to 10 if ``min_stock`` is unset (legacy rows).
        """
        threshold = self.min_stock if self.min_stock is not None else 10
        return self.stock_quantity <= threshold

    @property
    def is_selling_at_loss(self) -> bool:
        """True when the configured sale price is below acquisition cost."""
        return (self.cost_price or 0) > 0 and (self.sale_price or 0) < (self.cost_price or 0)

class Ingredient(models.Model):
    """
    Ingredient/Raw Material Model
    
    Represents raw materials, supplies, and packaging components used in
    production. Includes lot tracking support and FIFO inventory management.
    
    Attributes:
        user: Ingredient owner (multi-tenant)
        name: Ingredient name
        code: Unique code for lot identification (e.g., "MGS", "VITC")
        type: raw_material or supply (packaging/other)
        unit: Measurement unit (kg, g, l, ml, u)
        cost_per_unit: Purchase cost per unit
        stock_quantity: Current stock quantity
        min_stock: Minimum stock threshold for alerts (optional)
    
    Related Models:
        - Recipe: via ingredient FK
        - IngredientLot: via traceability.IngredientLot
        - BomLine: via production.BomLine
    
    Examples:
        >>> ingredient = Ingredient.objects.create(
        ...     code="MGS",
        ...     name="Magnesium Citrate",
        ...     type="raw_material",
        ...     unit="kg",
        ...     cost_per_unit=Decimal('150.00'),
        ...     stock_quantity=Decimal('100.50'),
        ...     min_stock=Decimal('10.00')
        ... )
        >>> str(ingredient)
        'Magnesium Citrate (Materia Prima (Fórmula) - kg)'
    
    Meta:
        unique code constraint for lot tracking
    """
    
    INGREDIENT_TYPES = [
        ('raw_material', 'Materia Prima (Fórmula)'),
        ('supply', 'Insumo (Packaging/Otros)'),
    ]
    
    UNIT_CHOICES = [
        ('kg', 'Kilogramos'),
        ('g', 'Gramos'),
        ('l', 'Litros'),
        ('ml', 'Mililitros'),
        ('u', 'Unidades')
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Ingredient owner"
    )
    name = models.CharField(
        max_length=200,
        help_text="Ingredient name"
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Unique code for lot identification (e.g., MGS, CIT, VITC)"
    )
    type = models.CharField(
        max_length=20,
        choices=INGREDIENT_TYPES,
        default='raw_material',
        help_text="Ingredient type: raw material or supply"
    )
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default='g',
        help_text="Measurement unit"
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        help_text="Purchase cost per unit"
    )
    stock_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        help_text="Current stock quantity"
    )
    min_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        help_text="Minimum stock threshold for alerts"
    )
    
    class Meta:
        verbose_name = "Ingredient"
        verbose_name_plural = "Ingredients"
        ordering = ['code', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['type']),
            models.Index(fields=['stock_quantity']),
        ]
    
    def __str__(self) -> str:
        """Return ingredient name with type and unit."""
        return f"{self.name} ({self.get_type_display()} - {self.unit})"
    
    @property
    def is_low_stock(self) -> bool:
        """
        Check if ingredient stock is below minimum threshold.
        
        Returns:
            True if stock is low or zero, False otherwise
        """
        return self.stock_quantity <= self.min_stock
    
    @property
    def is_raw_material(self) -> bool:
        """Check if this is a raw material (formula ingredient)."""
        return self.type == 'raw_material'
    
    @property
    def is_supply(self) -> bool:
        """Check if this is a supply (packaging/other)."""
        return self.type == 'supply'

class Recipe(models.Model):
    """
    Product Recipe Model (Simple BOM)
    
    Defines ingredient requirements for producing a single unit of a product.
    This is a simplified Bill of Materials (BOM) - for advanced BOMs,
    see production.BillOfMaterial.
    
    Attributes:
        user: Recipe owner
        product: Product this recipe is for
        ingredient: Required ingredient
        quantity: Amount of ingredient needed per product unit
    
    Related Models:
        - Product: via product FK
        - Ingredient: via ingredient FK
    
    Examples:
        >>> recipe = Recipe.objects.create(
        ...     product=product,
        ...     ingredient=magnesium,
        ...     quantity=Decimal('250.00')
        ... )
        >>> str(recipe)
        'Magnesium Plus 500g needs 250.00kg of Magnesium Citrate'
    
    Note:
        This model is kept for backward compatibility. New implementations
        should use production.BillOfMaterial for advanced features like
        percentage-based recipes and differentiated raw material vs supply costing.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Recipe owner"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='recipes',
        help_text="Product this recipe produces"
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='used_in_recipes',
        help_text="Required ingredient"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Quantity required per product unit"
    )

    class Meta:
        verbose_name = "Recipe"
        verbose_name_plural = "Recipes"
        unique_together = ['product', 'ingredient']
        ordering = ['product', 'ingredient']

    def __str__(self) -> str:
        """Return human-readable recipe description."""
        return f"{self.product.name} needs {self.quantity}{self.ingredient.unit} of  {self.ingredient.name}"

# Deprecated ProductionOrder in favor of production app?
# We agreed to keep existing functions, but user asked to "integres o reorganices".
# It is better to DEPRECATE this model if we are introducing a better one in 'production' app,
# OR we simply rename/migrate this one.
# For now, I will comment it out or leave it separate. If I remove it, I break existing code.
# The user said "no saques las que tenemos sino agregalas".
# So I will keep this simple model for backward compatibility or simplistic usage, 
# BUT the new FEATURES asked for (MRP, Lote) will use the new structure.
# I will Add the new models HERE.

class ProductionOrder(models.Model):
    # LEGACY / SIMPLE Production Order
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pendiente'), ('completed', 'Completado')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.quantity})"

class Batch(models.Model):
    """
    Lote y Vencimiento.
    Can apply to Ingredients (purchased) or Products (produced).
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Can be one or the other
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='batches')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name='batches')
    
    number = models.CharField(max_length=100, help_text="Número de Lote")
    expiration_date = models.DateField(null=True, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Stock actual en este lote")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        item_name = self.product.name if self.product else (self.ingredient.name if self.ingredient else "?")
        return f"Lote {self.number} - {item_name}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.product and not self.ingredient:
            raise ValidationError("Batch must belong to a Product or Ingredient")

class SupplierPrice(models.Model):
    """
    Gestión de Precios por Proveedor.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # We need to import Provider from finance. 
    # To avoid circular import at module level, we use string reference if possible, 
    # but since it's a different app, we must import usage.
    # Finance doesn't depend on Inventory, so it is safe to import Provider here?
    # Let's try.
    
    provider = models.ForeignKey('finance.Provider', on_delete=models.CASCADE, related_name='price_lists')
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='supplier_prices')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name='supplier_prices')
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='ARS')
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [
            ('provider', 'product'),
            ('provider', 'ingredient')
        ]

    def __str__(self):
        item = self.product or self.ingredient
        return f"{self.provider} - {item} - ${self.price}"
