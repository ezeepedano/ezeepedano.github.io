from django.db import models
from django.contrib.auth.models import User
from inventory.models import Product, Ingredient

class WorkCenter(models.Model):
    """
    Represents a location or machine where production takes place.
    Used for cost calculation.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    hourly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Costo por hora de operación")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class BillOfMaterial(models.Model):
    """
    Defines the structure of a product (Recipe/Formula).
    Replaces the simple 'Recipe' model in Inventory for advanced use cases.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # Deprecated: usage of singular product. Moving to M2M 'products'.
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='old_boms', null=True, blank=True)
    products = models.ManyToManyField(Product, related_name='boms', blank=True)
    name = models.CharField(max_length=200, help_text="Ej: Fórmula Estándar 2024")
    code = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, help_text="Cantidad producida con esta receta")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.product:
            return f"{self.product.name} ({self.name})"
        return self.name

class BomLine(models.Model):
    """
    Component of a BOM. Can be an Ingredient OR another Product (sub-assembly).
    """
    bom = models.ForeignKey(BillOfMaterial, on_delete=models.CASCADE, related_name='lines')
    
    # Can point to Ingredient (Raw Material) OR Product (Semi-finished)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True)
    component_product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='used_in_boms')
    
    quantity = models.DecimalField(max_digits=10, decimal_places=4, help_text="Cantidad requerida")
    scrap_factor = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="% de desperdicio estimado")
    
    def __str__(self):
        item_name = self.ingredient.name if self.ingredient else (self.component_product.name if self.component_product else "Unknown")
        return f"{self.quantity} of {item_name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.ingredient and not self.component_product:
            raise ValidationError("Debe especificar un Ingrediente o un Producto componente.")
        if self.ingredient and self.component_product:
            raise ValidationError("No puede especificar ambos (Ingrediente y Producto).")

class ProductionOrder(models.Model):
    """
    Order to produce X amount of Product.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'),
        ('IN_PROGRESS', 'En Proceso'),
        ('DONE', 'Finalizado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='production_orders')
    code = models.CharField(max_length=50, unique=True, default="WIP")
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='production_orders')
    bom = models.ForeignKey(BillOfMaterial, on_delete=models.PROTECT, null=True, blank=True, related_name='production_orders')
    
    quantity_to_produce = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_produced = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Link to origin (Sale Order, Manual, Stock Rule)
    origin = models.CharField(max_length=200, blank=True, null=True, help_text="Documento de origen (ej. SO001)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.product.name}"
