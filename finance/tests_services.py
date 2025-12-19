from django.test import TestCase
from decimal import Decimal
from datetime import date
from .models import FixedCost, MonthlyExpense, Purchase
from .services import ExpenseService, FinanceReportService

class ExpenseServiceTests(TestCase):
    def setUp(self):
        self.rent = FixedCost.objects.create(name="Alquiler", amount=Decimal('50000.00'), due_day=5)
        self.internet = FixedCost.objects.create(name="Internet", amount=Decimal('3000.00'), due_day=15)

    def test_generate_expenses_creates_records(self):
        # Generate for 2024-01
        created, updated = ExpenseService.generate_monthly_expenses_from_templates(2024, 1)
        
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        
        expenses = MonthlyExpense.objects.filter(month=date(2024, 1, 1))
        self.assertEqual(expenses.count(), 2)
        
        rent_expense = expenses.get(name="Alquiler")
        self.assertEqual(rent_expense.amount, Decimal('50000.00'))
        self.assertEqual(rent_expense.due_date, date(2024, 1, 5))

    def test_generate_expenses_updates_unpaid_only(self):
        # Initial create
        ExpenseService.generate_monthly_expenses_from_templates(2024, 1)
        
        # Modify Template amount
        self.rent.amount = Decimal('60000.00')
        self.rent.save()
        
        # Run generate again
        created, updated = ExpenseService.generate_monthly_expenses_from_templates(2024, 1)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 2) # Both updated, actually checked
        
        # Verify Rent updated because it is NOT paid
        rent_expense = MonthlyExpense.objects.get(name="Alquiler", month=date(2024, 1, 1))
        self.assertEqual(rent_expense.amount, Decimal('60000.00'))

    def test_generate_avoids_paid_updates(self):
        # Initial create
        ExpenseService.generate_monthly_expenses_from_templates(2024, 1)
        
        # Mark as Paid
        rent_expense = MonthlyExpense.objects.get(name="Alquiler", month=date(2024, 1, 1))
        rent_expense.is_paid = True
        rent_expense.save()
        
        # Modify Template amount
        self.rent.amount = Decimal('99999.00')
        self.rent.save()
        
        # Run generate
        ExpenseService.generate_monthly_expenses_from_templates(2024, 1)
        
        rent_expense.refresh_from_db()
        # Should remain original amount
        self.assertEqual(rent_expense.amount, Decimal('50000.00'))


class FinanceReportServiceTests(TestCase):
    def setUp(self):
        # Setup expenses for 2024-01
        self.expense1 = MonthlyExpense.objects.create(
            name="Exp1", 
            amount=Decimal('100.00'),
            month=date(2024, 1, 1),
            due_date=date(2024, 1, 5)
        )
        self.expense2 = MonthlyExpense.objects.create(
            name="Exp2", 
            amount=Decimal('50.00'), 
            is_paid=True, # Paid
            month=date(2024, 1, 1),
            due_date=date(2024, 1, 10)
        )
        # Setup purchase
        self.purchase = Purchase.objects.create(
            date=date(2024, 1, 15),
            amount=Decimal('500.00'),
            description="Test Purchase"
        )

    def test_dashboard_context(self):
        context = FinanceReportService.get_dashboard_context(2024, 1)
        
        self.assertEqual(context['total_amount'], Decimal('150.00'))
        self.assertEqual(context['total_paid'], Decimal('50.00'))
        self.assertEqual(context['total_pending'], Decimal('100.00'))
        
        # Verify Purchase included
        self.assertEqual(context['total_purchase_amount'], Decimal('500.00'))
        self.assertEqual(context['purchases'].count(), 1)
