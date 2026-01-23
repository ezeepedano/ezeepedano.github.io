from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

# Import models
from sales.models import Sale
from finance.models import CashMovement
from .models import JournalEntry, JournalItem, Account
from inventory.models import ProductionOrder
from hr.models import Payroll
from finance.models import Asset

def get_account_by_code(code):
    try:
        return Account.objects.get(code=code)
    except Account.DoesNotExist:
        return None

@receiver(post_save, sender=Sale)
def create_journal_entry_for_sale(sender, instance, created, **kwargs):
    """
    Automates Accrual Accounting for Sales.
    Dr. Accounts Receivable (Deudores por Ventas) - 1.1.02.01
    Cr. Sales Revenue (Ventas de Mercaderías) - 4.1.01
    """
    # Idempotency check
    if JournalEntry.objects.filter(reference=f"SALE-{instance.id}").exists():
        return
        
    # Only process if items exist
    if not instance.items.exists():
        return
        
    # Get Accounts
    receivable_acc = get_account_by_code('1.1.02.01') # Deudores por Ventas
    revenue_acc = get_account_by_code('4.1.01')       # Ventas de Mercaderías
    
    if not receivable_acc or not revenue_acc:
        # If accounts don't exist (e.g. seed not run), skip to avoid erroring the Main Sale Flow
        return

    # 1. Create Journal Entry Header
    journal = JournalEntry.objects.create(
        date=instance.date,
        description=f"Venta #{instance.id} - {instance.customer}",
        reference=f"SALE-{instance.id}",
        created_by=instance.user,
        posted=True
    )
    
    # 2. Create Items
    # Debit: Deudores (Asset Increase)
    JournalItem.objects.create(
        journal_entry=journal,
        account=receivable_acc,
        partner=instance.customer,
        debit=instance.total,
        credit=0,
        description="Venta a Crédito"
    )
    
    # Credit: Ventas (Revenue Increase)
    JournalItem.objects.create(
        journal_entry=journal,
        account=revenue_acc,
        partner=instance.customer,
        debit=0,
        credit=instance.total,
        description="Ingreso por Venta"
    )

    # 3. Cost of Goods Sold (CMV)
    # Dr. CMB (Egresos) - 5.1.01
    # Cr. Mercaderías (Activo) - 1.1.03.01
    
    # Calculate Total Cost of Sale
    cogs_amount = Decimal('0.00')
    # Use items.all() - REQUIRES items to be present when Sale is saved.
    for item in instance.items.all():
        if item.product and item.product.cost_price:
            cogs_amount += (item.product.cost_price * item.quantity)
            
    if cogs_amount > 0:
        cogs_acc = get_account_by_code('5.1.01')      # Costo de Mercaderías Vendidas
        inventory_acc = get_account_by_code('1.1.03.01') # Mercaderías de Reventa
        
        if cogs_acc and inventory_acc:
             JournalItem.objects.create(
                journal_entry=journal,
                account=cogs_acc,
                debit=cogs_amount,
                credit=0,
                description="Costo de Venta"
            )
             JournalItem.objects.create(
                journal_entry=journal,
                account=inventory_acc,
                debit=0,
                credit=cogs_amount,
                description="Salida de Mercadería"
            )

from finance.models import Purchase, MonthlyExpense

@receiver(post_save, sender=Purchase)
def create_journal_entry_for_purchase(sender, instance, created, **kwargs):
    """
    Automates Accrual Accounting for Purchases.
    Dr. Asset/Expense (Mercaderías / Gastos)
    Cr. Accounts Payable (Proveedores) - 2.1.01.01
    """
    if not created: 
        return

    # Accounts
    payable_acc = get_account_by_code('2.1.01.01') # Proveedores
    
    # Determine Debit Account (Asset vs Expense)
    # Simple logic: If it has a "Stock" related category, it is Asset. Note: Real world needs smarter mapping.
    # For MVP: Default to 'Mercaderías de Reventa' (Asset) 1.1.03.01
    expense_acc = get_account_by_code('1.1.03.01') 

    if not payable_acc or not expense_acc:
        return

    journal = JournalEntry.objects.create(
        date=instance.date,
        description=f"Compra #{instance.id} - {instance.provider}",
        reference=f"PURCH-{instance.id}",
        created_by=instance.user,
        posted=True
    )

    # Dr. Asset/Expense
    JournalItem.objects.create(journal_entry=journal, account=expense_acc, debit=instance.amount, credit=0)
    
    # Cr. Payable
    JournalItem.objects.create(journal_entry=journal, account=payable_acc, debit=0, credit=instance.amount)


@receiver(post_save, sender=MonthlyExpense)
def create_journal_entry_for_monthly_expense(sender, instance, created, **kwargs):
    """
    Automates Accrual for Recurring Expenses (Rent, Internet).
    Dr. Expense (Alquileres / Servicios)
    Cr. Accounts Payable (Proveedores/Deudas)
    """
    if not created:
        return

    payable_acc = get_account_by_code('2.1.01.01') # Proveedores (generic)
    
    # Map Expense Type
    # This relies on string matching or we need a 'mapping' model.
    target_code = '5.2.99' # Gastos Varios default
    name_lower = instance.name.lower()
    
    if 'alquiler' in name_lower:
        target_code = '5.2.01'
    elif 'internet' in name_lower or 'luz' in name_lower or 'gas' in name_lower:
        target_code = '5.2.02'
        
    expense_acc = get_account_by_code(target_code)

    if not payable_acc or not expense_acc:
        return

    journal = JournalEntry.objects.create(
        date=instance.month, # Use month start as accrual date? Or created_at?
        description=f"Gasto Mensual: {instance.name}",
        reference=f"EXP-{instance.id}",
        created_by=instance.user,
        posted=True
    )

    # Dr. Expense
    JournalItem.objects.create(journal_entry=journal, account=expense_acc, debit=instance.amount, credit=0)
    
    # Cr. Payable
    JournalItem.objects.create(journal_entry=journal, account=payable_acc, debit=0, credit=instance.amount)


@receiver(post_save, sender=CashMovement)
def create_journal_entry_for_cash_movement(sender, instance, created, **kwargs):
    """
    Automates Cash/Bank movements (Payments and Collections).
    """
    if not created:
        return

    # Cash Account (Asset)
    cash_ledger_acc = get_account_by_code('1.1.01.01')  # Default to Caja
    # TODO: Map instance.account.name to specific ledger account (Banco Galicia vs Caja)
    
    if not cash_ledger_acc:
        return

    # INCOMING MONEY (Cobros)
    if instance.type == 'IN':
        # Dr. Cash
        # Cr. Payer (Deudores)
        
        credit_acc_code = '1.1.02.01' # Deudores
        if instance.category == 'LOAN':
             credit_acc_code = '2.1.01' # Deuda (New Loan)
             
        credit_acc = get_account_by_code(credit_acc_code)
        
        if credit_acc:
            journal = JournalEntry.objects.create(
                date=instance.date,
                description=f"Ingreso #{instance.id}: {instance.description or instance.get_category_display()}",
                reference=f"CASH-IN-{instance.id}",
                created_by=instance.user,
                posted=True
            )
            JournalItem.objects.create(journal_entry=journal, account=cash_ledger_acc, debit=instance.amount, credit=0)
            JournalItem.objects.create(journal_entry=journal, account=credit_acc, debit=0, credit=instance.amount)

    # OUTGOING MONEY (Pagos)
    elif instance.type == 'OUT':
        # Dr. Payee (Proveedores) - settling the debt created by Purchase/Expense
        # Cr. Cash
        
        debit_acc_code = '2.1.01.01' # Proveedores
        
        # If it's a direct expense without prior accrual (e.g. ad-hoc taxi), we should debit Expense directly.
        # But we assume 'PURCHASE' and 'EXPENSE' categories usually come from the Purchase flow?
        # Use simple logic: Always debit 'Proveedores' for PURCHASES/EXPENSES to close the loop.
        
        debit_acc = get_account_by_code(debit_acc_code)
        
        if debit_acc:
             journal = JournalEntry.objects.create(
                date=instance.date,
                description=f"Pago #{instance.id}: {instance.description or instance.get_category_display()}",
                reference=f"CASH-OUT-{instance.id}",
                created_by=instance.user,
                posted=True
            )
             JournalItem.objects.create(journal_entry=journal, account=debit_acc, debit=instance.amount, credit=0)
             JournalItem.objects.create(journal_entry=journal, account=cash_ledger_acc, debit=0, credit=instance.amount)

@receiver(post_save, sender=ProductionOrder)
def create_journal_entry_for_production(sender, instance, created, **kwargs):
    """
    Automates Manufacturing Accounting.
    Dr. Finished Goods (Asset)
    Cr. Raw Materials (Asset)
    """
    if not created or instance.status != 'completed':
        return

    # Accounts
    finished_goods_acc = get_account_by_code('1.1.03.01') # Mercaderías (Finished)
    raw_materials_acc = get_account_by_code('1.1.03.02') # Materias Primas
    
    # If no specific Raw Material account, use generic stock for now
    if not raw_materials_acc:
        raw_materials_acc = get_account_by_code('1.1.03.01')

    if not finished_goods_acc or not raw_materials_acc:
        return

    # Calculate Total Cost of Production
    # Assuming Product Cost * Quantity produced
    total_cost = instance.product.cost_price * instance.quantity
    
    if total_cost <= 0:
        return

    journal = JournalEntry.objects.create(
        date=instance.created_at,
        description=f"Producción #{instance.id} - {instance.product.name}",
        reference=f"PROD-{instance.id}",
        created_by=instance.user,
        posted=True
    )

    # Dr. Finished Goods
    JournalItem.objects.create(journal_entry=journal, account=finished_goods_acc, debit=total_cost, credit=0)
    
    # Cr. Raw Materials
    JournalItem.objects.create(journal_entry=journal, account=raw_materials_acc, debit=0, credit=total_cost)


@receiver(post_save, sender=Payroll)
def create_journal_entry_for_payroll(sender, instance, created, **kwargs):
    """
    Automates Payroll Accrual.
    Dr. Salaries Expense (Sueldos y Jornales) - 5.2.03
    Cr. Salaries Payable (Sueldos a Pagar) - 2.1.02
    """
    if not created:
        return

    expense_acc = get_account_by_code('5.2.03') # Sueldos y Jornales
    payable_acc = get_account_by_code('2.1.02') # Sueldos a Pagar
    
    if not expense_acc or not payable_acc:
        return
        
    total_cost = instance.basic_salary # Gross Salary is the expense
    
    if total_cost <= 0:
        return

    journal = JournalEntry.objects.create(
        date=instance.period, 
        description=f"Liquidación Sueldos: {instance.employee}",
        reference=f"PAYROLL-{instance.id}",
        posted=True
    )

    # Dr. Expense
    JournalItem.objects.create(journal_entry=journal, account=expense_acc, debit=total_cost, credit=0)
    
    # Cr. Payable
    JournalItem.objects.create(journal_entry=journal, account=payable_acc, debit=0, credit=total_cost)


@receiver(post_save, sender=Asset)
def create_journal_entry_for_asset(sender, instance, created, **kwargs):
    """
    Automates Asset Acquisition.
    """
    pass
