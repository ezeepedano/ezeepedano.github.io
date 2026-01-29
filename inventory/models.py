from django.db import models
from django.contrib.auth.models import User
# We must defer import of Provider to avoid circular deps if Provider is in finance
# but usually it's better to put models logic where it belongs. 
# Provider was in finance.models. We will import it normally.
# However, if finance imports inventory, we have a cycle.
# finance.models imports nothing from inventory. Good.

class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, help_text="Stock Keeping Unit")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    net_weight = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, help_text="Peso neto por unidad (para cálculo de recetas)")
    unit_measure = models.CharField(max_length=10, choices=[('g', 'Gramos'), ('kg', 'Kilogramos'), ('ml', 'Mililitros'), ('l', 'Litros')], default='g')

    stock_quantity = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sku} - {self.name}"

class Ingredient(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    INGREDIENT_TYPES = [
        ('raw_material', 'Materia Prima (Fórmula)'),
        ('supply', 'Insumo (Packaging/Otros)'),
    ]
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=INGREDIENT_TYPES, default='raw_material')
    unit = models.CharField(max_length=20, choices=[('kg', 'Kilogramos'), ('g', 'Gramos'), ('l', 'Litros'), ('ml', 'Mililitros'), ('u', 'Unidades')], default='g')
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    def __str__(self):
        return f"{self.name} ({self.get_type_display()} - {self.unit})"

class Recipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recipes')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cantidad requerida por unidad de producto")

    def __str__(self):
        return f"{self.product.name} needs {self.quantity}{self.ingredient.unit} of {self.ingredient.name}"

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
