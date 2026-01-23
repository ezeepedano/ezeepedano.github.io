from decimal import Decimal
from django.utils import timezone
from datetime import date
from django.db import transaction
from .models import CashMovement, Account

class FinanceService:
    @staticmethod
    def register_payment(target_object, account, amount, date=None, description=None):
        """
        Registers a payment for a Sale or Purchase.
        1. Creates CashMovement (IN for Sale, OUT for Purchase).
        2. Updates target_object (paid_amount, payment_status, is_paid).
        """
        if not date:
            date = timezone.now()
            
        model_name = target_object._meta.model_name # 'sale' or 'purchase'
        
        # Determine Direction and Category
        if model_name == 'sale':
            direction = 'IN'
            category = 'SALE'
        elif model_name == 'purchase':
            direction = 'OUT'
            category = 'PURCHASE'
        else:
            raise ValueError(f"Unsupported object for payment: {model_name}")

        with transaction.atomic():
            # 1. Create Movement
            movement = CashMovement.objects.create(
                user=target_object.user,
                account=account,
                amount=amount,
                type=direction,
                category=category,
                date=date,
                description=description or f"Pago por {target_object}",
                content_object=target_object 
            )
            
            # 2. Update Balance
            # Assumes target_object has 'paid_amount', 'amount'/'total', 'payment_status'
            current_paid = target_object.paid_amount or Decimal('0.00')
            target_object.paid_amount = current_paid + amount
            
            # Check Total
            total = getattr(target_object, 'total', None) or getattr(target_object, 'amount', Decimal('0.00'))
            
            if target_object.paid_amount >= total:
                target_object.payment_status = 'PAID'
                target_object.is_paid = True # Legacy sync
            elif target_object.paid_amount > 0:
                target_object.payment_status = 'PARTIAL'
                target_object.is_paid = False
            else:
                target_object.payment_status = 'PENDING'
                target_object.is_paid = False
                
            target_object.save()
            
        return movement

# --- Legacy Services (Restored) ---

class FinanceReportService:
    @staticmethod
    def get_dashboard_context(year, month, user):
        from .models import MonthlyExpense, FixedCost, Purchase
        from django.db.models import Sum

        expenses = MonthlyExpense.objects.filter(user=user, month__year=year, month__month=month)
        purchases = Purchase.objects.filter(user=user, date__year=year, date__month=month)
        
        total_expenses = expenses.aggregate(Sum('real_amount'))['real_amount__sum'] or Decimal('0.00')
        total_purchases = purchases.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        paid_expenses = expenses.filter(is_paid=True).aggregate(Sum('real_amount'))['real_amount__sum'] or 0
        pending_expenses = total_expenses - paid_expenses
        
        return {
            'monthly_expenses': expenses,
            'purchases': purchases,
            'total_expenses': total_expenses,
            'total_purchase_amount': total_purchases, # Matches view usage
            'total_paid': paid_expenses,
            'total_pending': pending_expenses,
        }

class ExpenseService:
    @staticmethod
    def generate_monthly_expenses_from_templates(year, month, user):
        from .models import MonthlyExpense, FixedCost
        
        definitions = FixedCost.objects.filter(user=user)
        created_count = 0
        updated_count = 0 # Not heavily used but returned by view
        
        for defi in definitions:
            # Check if exists
            obj, created = MonthlyExpense.objects.get_or_create(
                user=user,
                fixed_cost=defi,
                month=date(year, month, 1),
                defaults={
                    'name': defi.name,
                    'real_amount': defi.amount,
                    'due_date': date(year, month, min(defi.due_day, 28)), # Simple logic
                    'category': defi.category
                }
            )
            if created:
                created_count += 1
            # We don't update existing automatically to preserve manual edits
                
        return created_count, updated_count

    @staticmethod
    def toggle_payment_status(expense):
        expense.is_paid = not expense.is_paid
        if expense.is_paid:
            expense.payment_date = timezone.now()
        else:
            expense.payment_date = None
        expense.save()
        return "PAGADO" if expense.is_paid else "PENDIENTE"

