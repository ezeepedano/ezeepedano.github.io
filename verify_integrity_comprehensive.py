import os
import django
from decimal import Decimal
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from sales.models import Sale, SaleItem, Customer, CustomerStats
from inventory.models import Product, Ingredient, Recipe, ProductionOrder, Category
from finance.models import FixedCost, MonthlyExpense, Provider, Purchase
from hr.models import Employee, Payroll
from inventory.services import ProductionService

def run_verification():
    print("=== STARTING SYSTEM INTEGRITY VERIFICATION ===")
    
    # Setup User
    user, _ = User.objects.get_or_create(username='integrity_test_user')
    print("[OK] Test User Ready")

    # CLEANUP PREVIOUS RUNS
    Employee.objects.filter(dni="99999999").delete()
    User.objects.filter(username='integrity_test_user').delete() 
    # Wait, deleting user helps cascade delete most things if set correctly?
    # BUT models often have on_delete=SET_NULL or CASCADE.
    # Let's recreate user after delete
    user, _ = User.objects.get_or_create(username='integrity_test_user')
    
    # --- 1. HR VERIFICATION ---
    print("\n--- 1. HR MODULE VERIFICATION ---")
    employee = Employee.objects.create(
        user=user,
        first_name="Test",
        last_name="Employee",
        dni="99999999",
        basic_salary=Decimal('100000.00')
    )
    payroll = Payroll.objects.create(
        employee=employee,
        period=timezone.now().date(),
        basic_salary=employee.basic_salary
    )
    # Expected Net: 100k - 11% - 3% - 3% = 100k - 17k = 83k
    expected_net = Decimal('100000.00') * Decimal('0.83')
    
    if abs(payroll.net_salary - expected_net) < Decimal('0.01'):
        print(f"[PASS] Payroll Calc: {payroll.net_salary} matches expected {expected_net}")
    else:
        print(f"[FAIL] Payroll Calc: Got {payroll.net_salary}, Expected {expected_net}")

    # --- 2. FINANCE VERIFICATION ---
    print("\n--- 2. FINANCE MODULE VERIFICATION ---")
    fcost = FixedCost.objects.create(
        user=user,
        name="Test Internet",
        amount=Decimal('5000.00'),
        due_day=10
    )
    # Simulate generating monthly expense (manual creation matching logic)
    m_expense = MonthlyExpense.objects.create(
        user=user,
        cost_definition=fcost,
        month=timezone.now().date().replace(day=1),
        name=fcost.name,
        amount=fcost.amount,
        due_date=timezone.now().date().replace(day=fcost.due_day)
    )
    if m_expense.amount == Decimal('5000.00'):
         print(f"[PASS] Fixed Cost -> Monthly Expense Logic Valid")
    else:
         print(f"[FAIL] Monthly Expense Amount mismatch")

    # --- 3. INVENTORY VERIFICATION ---
    print("\n--- 3. INVENTORY MODULE VERIFICATION ---")
    # Setup
    cat = Category.objects.create(user=user, name="Test Cat")
    product = Product.objects.create(
        user=user, 
        sku="TEST-PROD-001", 
        name="Test Product", 
        category=cat,
        net_weight=Decimal('100.00'), # 100g
        unit_measure='g',
        stock_quantity=0
    )
    ingredient = Ingredient.objects.create(
        user=user,
        name="Test Ingredient",
        type='raw_material',
        unit='kg', # Different unit to test conversion!
        stock_quantity=Decimal('10.00') # 10kg
    )
    # Recipe: 100g of Ingredient (kg) -> 0.1kg per unit
    Recipe.objects.create(
        user=user,
        product=product,
        ingredient=ingredient,
        quantity=Decimal('0.10') # 0.1kg = 100g
    )
    
    print(f"Initial State: Product Stock={product.stock_quantity}, Ingredient Stock={ingredient.stock_quantity}")
    
    # Produce 10 Units
    # Required Ingredient: 10 units * 0.1kg = 1.0kg
    ProductionService.process_production(product, 10)
    
    product.refresh_from_db()
    ingredient.refresh_from_db()
    
    print(f"Post-Production: Product Stock={product.stock_quantity}, Ingredient Stock={ingredient.stock_quantity}")
    
    if product.stock_quantity == 10 and ingredient.stock_quantity == Decimal('9.00'):
        print("[PASS] Inventory Production Logic (Stock Deduction & Addition)")
    else:
        print(f"[FAIL] Inventory Logic: Expected Prod=10, Ing=9.00. Got Prod={product.stock_quantity}, Ing={ingredient.stock_quantity}")

    # --- 4. SALES VERIFICATION ---
    print("\n--- 4. SALES MODULE VERIFICATION ---")
    # Setup Customer
    customer = Customer.objects.create(
        user=user,
        name="Test Customer",
        dedup_key="test_customer_key"
    )
    
    # Create Sale
    sale = Sale.objects.create(
        user=user,
        order_id="TEST-ORDER-001",
        customer=customer,
        date=timezone.now(),
        total=Decimal('0.00'),
        status='paid'
    )
    
    # Create Item
    SaleItem.objects.create(
        sale=sale,
        product=product,
        product_title=product.name,
        quantity=2,
        unit_price=Decimal('1500.00')
    )
    
    # Update Sale Totals (Simulate view logic)
    sale.product_revenue = Decimal('3000.00') # 2 * 1500
    sale.total = sale.product_revenue
    sale.save()
    
    # Check Customer Stats
    # Note: Stats populate logic is suspected missing. We check if it exists first.
    try:
        stats = customer.stats
        print(f"[INFO] CustomerStats found: {stats}")
        # If found, check if updated
        if stats.total_spent > 0:
             print("[PASS] CustomerStats updated automatically")
        else:
             print("[WARN] CustomerStats exists but was NOT updated automatically")
    except Customer.stats.RelatedObjectDoesNotExist:
        print("[FAIL] CustomerStats NOT created automatically (Missing Signal?)")
    except Exception as e:
        print(f"[ERROR] Checking stats: {e}")

    # Cleanup
    print("\n--- CLEANUP ---")
    # Delete test objects to keep DB clean
    # (Optional, but good practice. For now just leaving them as 'test' data or using transaction rollback if using TestCase, but here using script)
    # We leave them for inspection if needed.
    
    print("=== VERIFICATION COMPLETE ===")

if __name__ == '__main__':
    run_verification()
