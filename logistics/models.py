from django.db import models
from django.contrib.auth.models import User
from sales.models import Sale

class DeliveryZone(models.Model):
    """
    Geographic zone for logistics distribution.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Vehicle(models.Model):
    """
    Transportation vehicle.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, help_text="Ej: Camioneta Ford")
    plate = models.CharField(max_length=20, unique=True, help_text="Patente")
    
    capacity_volume = models.DecimalField(max_digits=10, decimal_places=2, help_text="Capacidad en m3", default=0)
    capacity_weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Capacidad en kg", default=0)
    
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_vehicles')
    
    def __str__(self):
        return f"{self.name} - {self.plate}"

class DeliveryRoute(models.Model):
    """
    A specific trip/route (Hoja de Ruta).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('READY', 'Listo para salir'),
        ('IN_TRANSIT', 'En Reparto'),
        ('COMPLETED', 'Completado'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes')
    
    zone = models.ForeignKey(DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ruta {self.date} - {self.vehicle}"

class DeliveryStop(models.Model):
    """
    A stop in the route, linked to a Sale Order.
    """
    STOP_STATUS = [
        ('PENDING', 'Pendiente'),
        ('DELIVERED', 'Entregado'),
        ('FAILED', 'No Entregado / Rechazado'),
    ]
    
    route = models.ForeignKey(DeliveryRoute, on_delete=models.CASCADE, related_name='stops')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='delivery_stops', help_text="Pedido asociado")
    
    sequence = models.PositiveIntegerField(default=0, help_text="Orden de visita")
    status = models.CharField(max_length=20, choices=STOP_STATUS, default='PENDING')
    
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"#{self.sequence} - {self.sale}"
