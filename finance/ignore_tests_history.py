import os
import django
from datetime import date

# Setup Django environment
import sys
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ERP.settings')
django.setup()

from finance.models import FixedCost, MonthlyExpense

def test_history_protection():
    print("--- Starting History Protection Test ---")
    
    # 1. Setup Data
    # Create a Cost Definition (e.g. Rent)
    rent_def = FixedCost.objects.create(
        name="Alquiler Test",
        amount=200000,
        due_day=10
    )
    print(f"Created Cost Definition: {rent_def.name} - ${rent_def.amount}")

    # 2. Generate June Expense
    june_date = date(2025, 6, 1)
    # Simulate View Logic for June
    MonthlyExpense.objects.update_or_create(
        month=june_date,
        cost_definition=rent_def,
        defaults={
            'name': rent_def.name,
            'amount': rent_def.amount, 
            'is_paid': False
        }
    )
    june_expense = MonthlyExpense.objects.get(month=june_date, cost_definition=rent_def)
    print(f"Generated June Expense: ${june_expense.amount} (Paid: {june_expense.is_paid})")

    # 3. Mark June as PAID
    june_expense.is_paid = True
    june_expense.save()
    print("Marked June as PAID.")

    # 4. Modify Cost Definition (Increase rent for July)
    rent_def.amount = 250000
    rent_def.save()
    print(f"Updated Cost Definition to ${rent_def.amount}")

    # 5. Generate July Expense
    july_date = date(2025, 7, 1)
    MonthlyExpense.objects.update_or_create(
        month=july_date,
        cost_definition=rent_def,
        defaults={
            'name': rent_def.name,
            'amount': rent_def.amount,
            'is_paid': False
        }
    )
    july_expense = MonthlyExpense.objects.get(month=july_date, cost_definition=rent_def)
    print(f"Generated July Expense: ${july_expense.amount}")

    # CHECK 1: Did July pick up new price?
    if july_expense.amount == 250000:
        print("PASS: July expense reflects new price.")
    else:
        print(f"FAIL: July expense is ${july_expense.amount}, expected $250000")

    # CHECK 2: Is June still $200k?
    june_expense.refresh_from_db()
    if june_expense.amount == 200000:
        print("PASS: June expense (Paid) preserved at old price.")
    else:
        print(f"FAIL: June expense changed to ${june_expense.amount}!")

    # 6. DANGEROUS STEP: Sync June Again
    # If user goes back to June and clicks "Sync", what happens?
    print("Simulating Sync on June...")
    
    # NEW REFLECTED LOGIC (Protected View Behavior):
    existing_expense = MonthlyExpense.objects.filter(cost_definition=rent_def, month=june_date).first()
    
    defaults = {
        'name': rent_def.name,
        # 'amount' is conditionally added
    }
    
    if existing_expense and existing_expense.is_paid:
        print("Logic Check: Expense is paid, preserving amount.")
        # Do NOT add amount to defaults
    else:
        defaults['amount'] = rent_def.amount

    MonthlyExpense.objects.update_or_create(
        month=june_date,
        cost_definition=rent_def,
        defaults=defaults
    )
    
    june_expense.refresh_from_db()
    if june_expense.amount == 200000:
        print("PASS: Paid June expense preserved after Sync.")
    else:
        print(f"FAIL WARNING: Paid June expense updated to ${june_expense.amount} after Sync!")

    # Cleanup
    rent_def.delete()
    print("--- Test Finished ---")

if __name__ == "__main__":
    try:
        test_history_protection()
    except Exception as e:
        print(f"Error: {e}")
