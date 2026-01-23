from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Account(models.Model):
    """
    Financial Account (Bank, Cash, Wallet).
    """
    ACCOUNT_TYPES = (
        ('CASH', 'Efectivo / Caja'),
        ('BANK', 'Banco'),
        ('WALLET', 'Billetera Virtual (MP, etc)'),
        ('OTHER', 'Otro'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='CASH')
    currency = models.CharField(max_length=10, default='ARS')
    
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, help_text="Saldo al inicio")
    opening_date = models.DateField(default=timezone.now, help_text="Fecha del saldo inicial")
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

class CashMovement(models.Model):
    """
    Tracks all real money movements (Cash Flow).
    """
    MOVEMENT_TYPES = (
        ('IN', 'Ingreso'),
        ('OUT', 'Egreso'),
    )
    
    CATEGORIES = (
        ('SALE', 'Venta'),
        ('EXPENSE', 'Gasto'),
        ('PURCHASE', 'Compra Insumos'),
        ('PAYROLL', 'Sueldos'),
        ('TAX', 'Impuestos'),
        ('LOAN', 'Préstamo/Financiamiento'),
        ('TRANSFER', 'Transferencia entre cuentas'),
        ('ADJUSTMENT', 'Ajuste'),
        ('OTHER', 'Otro'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text="Monto absoluto")
    type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='OTHER')
    
    # Linked Account
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='movements')
    
    # External ID for Deduplication (MP Import)
    external_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="ID externo para evitar duplicados (ej. MP)")
    
    description = models.TextField(blank=True, null=True)
    
    # Generic Link to Sale, Buy, Cost, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date.date()} - {self.get_type_display()} ${self.amount} ({self.account})"


COST_CATEGORIES = (
    ('ADMINISTRATIVE', 'Gastos Administrativos'),
    ('ADVERTISING', 'Publicidad y Marketing'),
    ('COMMERCIAL', 'Comisiones de Venta'),
    ('FINANCIAL', 'Costos Financieros y Bancarios'),
    ('FINANCING', 'Adelanto de Dinero / Intereses'),
    ('PLATFORM', 'Plataforma y Tecnología (Tienda Nube)'),
    ('LOGISTICS', 'Logística y Envíos'),
    ('INDIRECT', 'Costos Indirectos de Fabricación'),
    ('TAXES', 'Impuestos y Tasas'),
    ('OTHER', 'Otros Gastos'),
)

class FixedCost(models.Model):
    """Template for recurring monthly costs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_day = models.IntegerField(default=1, help_text="Day of the month (1-31)")
    
    category = models.CharField(max_length=20, choices=COST_CATEGORIES, default='OTHER')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ${self.amount}"

class MonthlyExpense(models.Model):
    """Actual expense instance for a specific month"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    cost_definition = models.ForeignKey(FixedCost, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    month = models.DateField(help_text="First day of the month for this expense")
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    category = models.CharField(max_length=20, choices=COST_CATEGORIES, default='OTHER')
    
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'name']
        unique_together = ['cost_definition', 'month'] # Prevent duplicate generation for same recurrent cost

    def __str__(self):
        return f"{self.name} ({self.month.strftime('%Y-%m')}) - ${self.amount}"

class Provider(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    
    # Structured Contact Info
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    cuit = models.CharField(max_length=20, blank=True, null=True, verbose_name="CUIT/Tax ID")
    website = models.URLField(blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True, help_text="Internal notes about this provider")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PurchaseCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100) # Uniqueness might need to be scoped to User
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Purchase categories"

    def __str__(self):
        return self.name

class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    provider = models.ForeignKey(Provider, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(PurchaseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=100, blank=True, null=True, help_text="Invoice number or internal code")
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Aging / Payments
    due_date = models.DateField(null=True, blank=True, help_text="Fecha de vencimiento")
    is_paid = models.BooleanField(default=False) # Legacy field, kept for compatibility, sync with status
    payment_status = models.CharField(max_length=20, choices=[('PENDING', 'Pendiente'), ('PARTIAL', 'Parcial'), ('PAID', 'Pagado')], default='PENDING')
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    @property
    def balance(self):
        return self.amount - self.paid_amount
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.payment_status in ['PENDING', 'PARTIAL'] and not self.due_date:
            raise ValidationError({'due_date': "Debe especificar una Fecha de Vencimiento para compras pendientes o parciales."})

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.provider} - ${self.amount}"

class AssetCategory(models.Model):
    """Category for Fixed Assets (e.g., Maquinaria, Muebles, Rodados)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Asset categories"

    def __str__(self):
        return self.name

class Asset(models.Model):
    """Fixed Assets / Bienes de Uso"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    purchase_date = models.DateField(default=timezone.now)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    provider = models.ForeignKey(Provider, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=200, blank=True, null=True, help_text="Where is this asset located?")
    
    quantity = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (${self.cost})"


