from django.db import models
from inventory.models import Product
from django.contrib.auth.models import User

class Customer(models.Model):
    """
    Customer profile extracted from MercadoLibre sales Excel.
    Deduplication is handled via `dedup_key` (hash of document or name+address).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    # Identity
    name = models.CharField(max_length=255, help_text="Comprador")
    
    # Document: prioritized from DNI column, fallback to parsed "Tipo y número de documento"
    document_raw = models.CharField(max_length=255, blank=True, null=True)
    document_type = models.CharField(max_length=50, blank=True, null=True)  # CUIT, DNI, etc.
    document_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Billing (Facturación al comprador)
    billing_name = models.CharField(max_length=255, blank=True, null=True, help_text="Datos personales o de empresa")
    billing_address = models.CharField(max_length=255, blank=True, null=True, help_text="Dirección")
    tax_condition = models.CharField(max_length=100, blank=True, null=True, help_text="Condición fiscal")
    
    # Shipping (Compradores section)
    shipping_address = models.CharField(max_length=255, blank=True, null=True, help_text="Domicilio")
    city = models.CharField(max_length=100, blank=True, null=True, help_text="Ciudad")
    state = models.CharField(max_length=100, blank=True, null=True, help_text="Estado/Provincia")
    postal_code = models.CharField(max_length=20, blank=True, null=True, help_text="Código postal")
    country = models.CharField(max_length=100, blank=True, null=True, help_text="País")
    
    
    # Deduplication key (unique hash)
    dedup_key = models.CharField(max_length=128, unique=True, db_index=True)

    has_open_claim = models.BooleanField(default=False, help_text="Tiene reclamo abierto")
    
    # Extra fields from migration
    first_purchase_date = models.DateTimeField(blank=True, null=True)
    last_purchase_date = models.DateTimeField(blank=True, null=True)
    is_wholesaler = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def safe_stats(self):
        """Bulletproof access to stats (handles missing OneToOne relation)."""
        try:
            return self.stats
        except Exception:
            return None



SALE_CHANNELS = (
    ('MERCADOLIBRE', 'Mercado Libre'),
    ('WHOLESALE', 'Mayorista'),
    ('TIENDANUBE', 'Tienda Nube'),
)

class Sale(models.Model):
    """
    A single sale/order from MercadoLibre.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=SALE_CHANNELS, default='MERCADOLIBRE')
    
    order_id = models.CharField(max_length=50, unique=True, help_text="# de venta")
    date = models.DateTimeField(help_text="Fecha de venta")
    status = models.CharField(max_length=100, help_text="Estado del pedido")
    
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    
    # Financial Summary
    total = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total (ARS)")
    product_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Ingresos por productos")
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Costos de envío")
    
    # Fees
    listing_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Cargo por venta + Costo fijo + Cuotas")
    taxes = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Impuestos")
    discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Descuentos")
    shipping_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Ingresos por envío")
    
    # Shipping & Buyer Details
    shipping_option = models.CharField(max_length=100, blank=True, null=True, help_text="Forma de entrega")
    tracking_number = models.CharField(max_length=100, blank=True, null=True, help_text="Número de seguimiento")
    buyer_dni = models.CharField(max_length=50, blank=True, null=True, help_text="DNI del comprador")
    buyer_address = models.TextField(blank=True, null=True, help_text="Domicilio")
    province = models.CharField(max_length=100, blank=True, null=True, help_text="Estado/Provincia")
    city = models.CharField(max_length=100, blank=True, null=True, help_text="Ciudad")
    zip_code = models.CharField(max_length=20, blank=True, null=True, help_text="Código postal")
    invoice_data = models.TextField(blank=True, null=True, help_text="Datos para facturación")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Order #{self.order_id} - {self.date.date()}"

    def get_mercadolibre_url(self):
        return f"https://www.mercadolibre.com.ar/ventas/{self.order_id}/detalle"


class SaleItem(models.Model):
    """
    Individual line item within a Sale.
    """
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    
    product_title = models.CharField(max_length=300)
    sku = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity}x {self.product_title}"


class CustomerStats(models.Model):
    """
    Aggregated metrics for a Customer.
    Calculated via signals or periodic tasks (or import process).
    """
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='stats')
    
    total_orders = models.PositiveIntegerField(default=0)
    total_units = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    avg_ticket = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_ticket = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    first_order_date = models.DateTimeField(null=True, blank=True)
    last_order_date = models.DateTimeField(null=True, blank=True)
    days_since_last_order = models.IntegerField(default=0)
    
    total_return_units = models.PositiveIntegerField(default=0)
    return_rate = models.FloatField(default=0.0)
    
    open_claims_count = models.PositiveIntegerField(default=0)
    closed_claims_count = models.PositiveIntegerField(default=0)
    mediated_claims_count = models.PositiveIntegerField(default=0)
    
    r_score = models.PositiveSmallIntegerField(default=0)
    f_score = models.PositiveSmallIntegerField(default=0)
    m_score = models.PositiveSmallIntegerField(default=0)
    
    segment = models.CharField(max_length=50, blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stats for {self.customer.name}"
