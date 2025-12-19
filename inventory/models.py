from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recipes')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cantidad requerida por unidad de producto")

    def __str__(self):
        return f"{self.product.name} needs {self.quantity}{self.ingredient.unit} of {self.ingredient.name}"

class ProductionOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pendiente'), ('completed', 'Completado')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.quantity})"
