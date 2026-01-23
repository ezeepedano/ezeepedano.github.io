from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class Account(models.Model):
    """
    Plan de Cuentas (Chart of Accounts).
    Hierarchical structure for financial tracking.
    """
    ACCOUNT_TYPES = (
        ('ASSET', 'Activo'),
        ('LIABILITY', 'Pasivo'),
        ('EQUITY', 'Patrimonio Neto'),
        ('REVENUE', 'Ingresos'),
        ('EXPENSE', 'Egresos'),
    )
    
    code = models.CharField(max_length=20, unique=True, help_text="Código jerárquico (ej. 1.1.01)")
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    
    is_reconcilable = models.BooleanField(default=False, help_text="Permite conciliación (ej. Bancos, Clientes)")
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Cuenta Contable'
        verbose_name_plural = 'Plan de Cuentas'

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    """
    Asiento Contable (Header).
    Represents a single transaction in the General Ledger.
    """
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255, help_text="Concepto del asiento")
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Referencia externa (ej. Factura #123)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Validation status
    posted = models.BooleanField(default=False, help_text="Si es True, el asiento es definitivo y afecta saldos.")

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Asiento Contable'
        verbose_name_plural = 'Libro Diario'

    def __str__(self):
        return f"{self.date} - {self.description}"

    @property
    def is_balanced(self):
        debits = sum(item.debit for item in self.items.all())
        credits = sum(item.credit for item in self.items.all())
        return debits == credits


class JournalItem(models.Model):
    """
    Imputación Contable (Line Item).
    A single line in a Journal Entry.
    """
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='items')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_items')
    partner = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, help_text="Cliente/Proveedor asociado")
    
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Movimiento Contable'
        verbose_name_plural = 'Movimientos'

    def __str__(self):
        return f"{self.account.code} | D: {self.debit} | C: {self.credit}"
    
    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Una línea no puede tener Debe y Haber simultáneamente.")
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("Los montos no pueden ser negativos.")
