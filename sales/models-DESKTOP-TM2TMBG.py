"""
Sales Models Module

Defines all sales-related models including customers, sales orders, line items,
and customer analytics. Includes automatic customer segmentation and deduplication.

Models:
    - Customer: Customer records with deduplication support
    - Sale: Sales orders with multi-channel support
    - SaleItem: Order line items
    - CustomerSegment: Customer categorization (VIP, Regular, Active, New)
    - CustomerStats: Denormalized customer analytics

Author: ERP Development Team
Created: 2025-01-01
Updated: 2026-02-04
"""

from typing import Optional
from decimal import Decimal
from django.db import models
from inventory.models import Product
from django.contrib.auth.models import User

class Customer(models.Model):
    """
    Represents a customer profile, potentially extracted from various sales channels.
    Deduplication is managed using a `dedup_key` (a hash of identifying information).

    Attributes:
        user (ForeignKey): Link to Django's built-in User model if the customer has an account.
        name (CharField): Full name of the customer.
        email (EmailField): Customer's email address.
        phone (CharField): Customer's phone number.
        document_raw (CharField): Raw document string from source.
        document_type (CharField): Type of identification document (e.g., CUIT, DNI).
        document_number (CharField): Number of the identification document.
        billing_name (CharField): Name for billing purposes.
        billing_address (CharField): Address for billing purposes.
        tax_condition (CharField): Customer's tax condition.
        shipping_address (CharField): Primary shipping address.
        city (CharField): City for shipping.
        state (CharField): State/Province for shipping.
        postal_code (CharField): Postal code for shipping.
        country (CharField): Country for shipping.
        dedup_key (CharField): Unique hash for customer deduplication.
        has_open_claim (BooleanField): Indicates if the customer has an active claim.
        first_purchase_date (DateTimeField): Date of the customer's first purchase.
        last_purchase_date (DateTimeField): Date of the customer's most recent purchase.
        is_wholesaler (BooleanField): Flag indicating if the customer is a wholesaler.
        is_blocked (BooleanField): Flag indicating if the customer is blocked.
        created_at (DateTimeField): Timestamp of when the record was created.
        updated_at (DateTimeField): Timestamp of when the record was last updated.

    Methods:
        __str__: Returns the customer's name.
        safe_stats: Safely retrieves customer statistics, handling missing relations.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    # Identity
    name = models.CharField(max_length=255, help_text="Comprador")
    email = models.EmailField(blank=True, null=True, help_text="Email")
    phone = models.CharField(max_length=100, blank=True, null=True, help_text="Teléfono")
    
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
    ('PARTICULAR', 'Particular'),
)

class Sale(models.Model):
    """
    A single sale/order from MercadoLibre.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=SALE_CHANNELS, default='MERCADOLIBRE')
    
    order_id = models.CharField(max_length=100, help_text="ID de pedido (Mercado Libre, etc)", blank=True, null=True)
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
    # Detailed Statuses (from sales channel)
    channel_payment_status = models.CharField(max_length=100, blank=True, null=True, help_text="Estado del pago (canal de venta)")
    shipping_status = models.CharField(max_length=100, blank=True, null=True, help_text="Estado del envío")
    
    # Financial Details
    currency = models.CharField(max_length=10, default='ARS', help_text="Moneda")
    payment_method = models.CharField(max_length=100, blank=True, null=True, help_text="Medio de pago")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID Transacción Pago")
    payment_date = models.DateTimeField(blank=True, null=True, help_text="Fecha de pago")

    # Aging / Accounts Receivable
    due_date = models.DateField(null=True, blank=True, help_text="Fecha de vencimiento / cobro esperado")
    payment_status = models.CharField(max_length=20, choices=[('PENDING', 'Pendiente'), ('PARTIAL', 'Parcial'), ('PAID', 'Pagado')], default='PAID', help_text="Estado de Cobranza") 
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monto Cobrado")
    
    @property
    def balance(self):
        return self.total - self.paid_amount

    # Notes
    buyer_notes = models.TextField(blank=True, null=True, help_text="Notas del comprador")
    seller_notes = models.TextField(blank=True, null=True, help_text="Notas del vendedor")
    
    # Shipping Extended
    shipping_date = models.DateTimeField(blank=True, null=True, help_text="Fecha de envío")
    recipient_name = models.CharField(max_length=255, blank=True, null=True, help_text="Nombre para el envío")
    recipient_phone = models.CharField(max_length=100, blank=True, null=True, help_text="Teléfono para el envío")
    
    invoice_data = models.TextField(blank=True, null=True, help_text="Datos para facturación")
    
    # Internal Flags
    stock_deducted = models.BooleanField(default=False, help_text="Stock descontado")

    def clean(self):
        from django.core.exceptions import ValidationError
        # Enforce due_date for receivables logic
        if self.payment_status in ['PENDING', 'PARTIAL'] and not self.due_date:
            raise ValidationError({'due_date': "Debe especificar una Fecha de Vencimiento para ventas pendientes o parciales."})

    def save(self, *args, **kwargs):
        # Ensure we run logic even if clean not called? No, clean is for forms usually.
        # But we can force it if needed. For now standard Django practice is clean() uses validation.
        # But let's set a default due_date = today if missing and pending? Better to error as requested "obligatorio".
        super().save(*args, **kwargs)

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
    return_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tasa de devolución (%)")
    
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


# ============================================================================
# QUOTATION / PRESUPUESTO
# ============================================================================

QUOTATION_STATUS = (
    ('DRAFT', 'Borrador'),
    ('SENT', 'Enviado'),
    ('ACCEPTED', 'Aceptado'),
    ('REJECTED', 'Rechazado'),
)

SALE_TYPE_CHOICES = (
    ('WHOLESALE', 'Mayorista'),
    ('RETAIL', 'Minorista'),
)

SALE_CONDITION_CHOICES = (
    ('CONTADO', 'Contado'),
    ('CTA_CTE', 'Cuenta Corriente'),
    ('CHEQUE', 'Cheque'),
    ('TRANSFERENCIA', 'Transferencia'),
)


class Quotation(models.Model):
    """
    Sales quotation / presupuesto de venta.
    Supports wholesale and retail pricing with IVA and discounts.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    number = models.CharField(max_length=20, unique=True, editable=False, help_text="Nro de presupuesto auto-generado")
    date = models.DateField(help_text="Fecha de emisión")
    valid_until = models.DateField(help_text="Válido hasta")
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quotations', help_text="Cliente"
    )
    sale_type = models.CharField(
        max_length=20, choices=SALE_TYPE_CHOICES, default='WHOLESALE',
        help_text="Tipo de venta"
    )
    sale_condition = models.CharField(
        max_length=20, choices=SALE_CONDITION_CHOICES, default='CTA_CTE',
        help_text="Condición de venta"
    )
    payment_terms = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Condiciones de pago (ej: 30 días)"
    )
    notes = models.TextField(
        blank=True, null=True,
        help_text="Observaciones / condiciones especiales"
    )
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Bonificación global %"
    )
    status = models.CharField(
        max_length=20, choices=QUOTATION_STATUS, default='DRAFT'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-pk']

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Sin cliente"
        return f"Presupuesto {self.number} - {customer_name}"

    def save(self, *args, **kwargs):
        if not self.number:
            # Query ALL quotations globally since number is unique across users
            last = Quotation.objects.order_by('-pk').first()
            if last and last.number:
                try:
                    seq = int(last.number.replace('P', '')) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.number = f"P{seq:05d}"
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        """Sum of all line totals before global discount."""
        return sum(item.line_total for item in self.items.all())

    @property
    def discount_amount(self):
        """Global discount amount."""
        return self.subtotal * (self.discount_pct / Decimal('100'))

    @property
    def net_gravado(self):
        """Subtotal minus global discount."""
        return self.subtotal - self.discount_amount

    @property
    def tax_amount(self):
        """Sum of IVA for each line (after global discount proportionally)."""
        total_iva = Decimal('0')
        sub = self.subtotal
        if sub == 0:
            return total_iva
        discount_factor = Decimal('1') - (self.discount_pct / Decimal('100'))
        for item in self.items.all():
            net_line = item.line_total * discount_factor
            total_iva += net_line * (item.iva_pct / Decimal('100'))
        return total_iva

    @property
    def total(self):
        """Final total = net_gravado + IVA."""
        return self.net_gravado + self.tax_amount


class QuotationItem(models.Model):
    """Individual line item within a Quotation."""
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.CharField(
        max_length=300, help_text="Descripción del producto"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Precio unitario"
    )
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Bonificación por línea %"
    )
    iva_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=21,
        help_text="% IVA"
    )

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f"{self.quantity}x {self.description}"

    @property
    def line_total(self):
        """quantity * unit_price * (1 - discount_pct/100)."""
        discount_factor = Decimal('1') - (self.discount_pct / Decimal('100'))
        return self.quantity * self.unit_price * discount_factor
