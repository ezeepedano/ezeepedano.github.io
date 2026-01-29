from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from inventory.models import Ingredient, Product
from production.models import ProductionOrder, BillOfMaterial
from datetime import date, timedelta


class IngredientLot(models.Model):
    """
    Representa un lote/bolsa específica de ingrediente con trazabilidad completa.
    Equivalente a las filas en DB_STOCK.xlsx del sistema anterior.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Identificación
    internal_id = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="ID interno generado automáticamente (ej: MP-MAL-001)"
    )
    ingredient = models.ForeignKey(
        Ingredient, 
        on_delete=models.PROTECT, 
        related_name='lots'
    )
    
    # Cantidades
    quantity_initial = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        help_text="Cantidad inicial al recibir (kg)"
    )
    quantity_current = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        help_text="Cantidad actual disponible (kg)"
    )
    
    # Trazabilidad del proveedor
    supplier_lot = models.CharField(
        max_length=100, 
        help_text="Lote del proveedor"
    )
    
    # Fechas
    received_date = models.DateField(auto_now_add=True)
    expiration_date = models.DateField(null=True, blank=True)
    
    # Estado
    is_active = models.BooleanField(
        default=True, 
        help_text="False si fue consumido totalmente o descartado"
    )
    is_wasted = models.BooleanField(
        default=False, 
        help_text="True si fue descartado por merma"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['received_date', 'created_at']  # FIFO ordering
        verbose_name = "Lote de Ingrediente"
        verbose_name_plural = "Lotes de Ingredientes"
    
    def __str__(self):
        return f"{self.internal_id} - {self.ingredient.name} ({self.quantity_current}/{self.quantity_initial} kg)"
    
    def is_near_expiry(self, days=90):
        """Verifica si el lote está próximo a vencer"""
        if not self.expiration_date:
            return False
        return (self.expiration_date - date.today()).days <= days
    
    def consume(self, quantity):
        """Consume una cantidad del lote"""
        if quantity > self.quantity_current:
            raise ValidationError(f"No hay suficiente stock. Disponible: {self.quantity_current} kg")
        
        self.quantity_current -= quantity
        if self.quantity_current <= 0:
            self.is_active = False
        self.save()


class ProductionBatch(models.Model):
    """
    Lote de producción con trazabilidad completa.
    Extiende el concepto de ProductionOrder agregando tracking de lotes.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('IN_PROGRESS', 'En Proceso'),
        ('COMPLETED', 'Completado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Identificación
    internal_lot_code = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Código de lote interno (ej: L-240130-01)"
    )
    
    # Relaciones
    production_order = models.ForeignKey(
        ProductionOrder, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='batches'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        related_name='production_batches'
    )
    bom = models.ForeignKey(
        BillOfMaterial, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        help_text="Receta utilizada"
    )
    
    # Cantidades
    quantity_produced = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        help_text="Cantidad producida (kg)"
    )
    
    # Fechas
    production_date = models.DateField(default=date.today)
    
    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Notas
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-production_date', '-created_at']
        verbose_name = "Lote de Producción"
        verbose_name_plural = "Lotes de Producción"
    
    def __str__(self):
        return f"{self.internal_lot_code} - {self.product.name} ({self.quantity_produced} kg)"


class BatchConsumption(models.Model):
    """
    Registro detallado de qué lotes de ingredientes se consumieron 
    en una producción específica. Esto permite trazabilidad completa.
    """
    production_batch = models.ForeignKey(
        ProductionBatch, 
        on_delete=models.CASCADE, 
        related_name='consumptions'
    )
    ingredient_lot = models.ForeignKey(
        IngredientLot, 
        on_delete=models.PROTECT, 
        related_name='usages'
    )
    ingredient = models.ForeignKey(
        Ingredient, 
        on_delete=models.PROTECT,
        help_text="Redundante pero útil para queries"
    )
    
    # Cantidad consumida de este lote específico
    quantity_consumed = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        help_text="Cantidad consumida de este lote (kg)"
    )
    
    # Si fue descartado como merma
    is_waste = models.BooleanField(
        default=False, 
        help_text="True si fue descartado como merma (< umbral)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['production_batch', 'ingredient']
        verbose_name = "Consumo de Lote"
        verbose_name_plural = "Consumos de Lotes"
    
    def __str__(self):
        waste_label = " [MERMA]" if self.is_waste else ""
        return f"{self.production_batch.internal_lot_code} - {self.ingredient_lot.internal_id}: {self.quantity_consumed} kg{waste_label}"


class StockAlert(models.Model):
    """
    Alertas automáticas de stock bajo o próximo a vencer.
    """
    ALERT_TYPES = [
        ('LOW_STOCK', 'Stock Bajo'),
        ('NEAR_EXPIRY', 'Próximo a Vencer'),
        ('EXPIRED', 'Vencido'),
    ]
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    
    # Puede ser alerta de ingrediente en general o de un lote específico
    ingredient = models.ForeignKey(
        Ingredient, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='alerts'
    )
    ingredient_lot = models.ForeignKey(
        IngredientLot, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='alerts'
    )
    
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alerta de Stock"
        verbose_name_plural = "Alertas de Stock"
    
    def __str__(self):
        status = "✓ Resuelta" if self.is_resolved else "⚠ Activa"
        return f"[{self.get_alert_type_display()}] {status} - {self.message[:50]}"


class TraceabilityConfig(models.Model):
    """
    Configuración global del sistema de trazabilidad.
    """
    # Umbral de merma (en kg)
    waste_threshold_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=3, 
        default=0.100,
        help_text="Si queda menos de esta cantidad, se descarta como merma (kg)"
    )
    
    # Umbral de stock bajo (en kg)
    low_stock_threshold_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=5.00,
        help_text="Alerta si el stock total está por debajo de este valor (kg)"
    )
    
    # Días antes de vencimiento para alertar
    expiry_alert_days = models.IntegerField(
        default=90,
        help_text="Días antes del vencimiento para generar alerta"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Trazabilidad"
        verbose_name_plural = "Configuraciones de Trazabilidad"
    
    def __str__(self):
        return f"Config - Merma: {self.waste_threshold_kg} kg, Stock Bajo: {self.low_stock_threshold_kg} kg"
    
    @classmethod
    def get_config(cls):
        """Obtiene o crea la configuración única"""
        config, created = cls.objects.get_or_create(pk=1)
        return config
