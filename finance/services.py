from datetime import date, timedelta
import calendar
from django.db.models import Sum, Q, Count
from django.utils import timezone
from .models import MonthlyExpense, Purchase, FixedCost

class ExpenseService:
    @staticmethod
    def generate_monthly_expenses_from_templates(year: int, month: int, user) -> tuple[int, int]:
        """
        Generates or updates monthly expenses based on FixedCost templates.
        Returns (created_count, updated_count).
        """
        target_month = date(year, month, 1)
        templates = FixedCost.objects.filter(user=user)
        created_count = 0
        updated_count = 0
        
        for t in templates:
            # Calculate due date
            try:
                due_date = date(year, month, min(t.due_day, calendar.monthrange(year, month)[1]))
            except ValueError:
                due_date = target_month

            # Check for existing expense
            existing_expense = MonthlyExpense.objects.filter(
                user=user,
                cost_definition=t, 
                month=target_month
            ).first()

            defaults = {
                'user': user,
                'name': t.name,
                'description': t.description,
                'due_date': due_date,
                'category': t.category,
            }

            # Only update amount if it's NOT paid (or doesn't exist yet)
            if not existing_expense or not existing_expense.is_paid:
                defaults['amount'] = t.amount

            expense, created = MonthlyExpense.objects.update_or_create(
                user=user,
                cost_definition=t,
                month=target_month,
                defaults=defaults
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
                
        return created_count, updated_count

    @staticmethod
    def toggle_payment_status(expense: MonthlyExpense) -> str:
        """Toggles the paid status of an expense."""
        expense.is_paid = not expense.is_paid
        if expense.is_paid:
            expense.payment_date = timezone.now().date()
        else:
            expense.payment_date = None
        expense.save()
        return "pagado" if expense.is_paid else "pendiente"


class FinanceReportService:
    @staticmethod
    def get_dashboard_context(view_year: int, view_month: int, user):
        """Builds the comprehensive context for the finance dashboard."""
        
        today = timezone.now().date()
        current_month_date = date(view_year, view_month, 1)
        
        # 1. Navigation Dates
        prev_month_date = (current_month_date - timedelta(days=1)).replace(day=1)
        next_month_date = (current_month_date + timedelta(days=32)).replace(day=1)

        # 2. Current Month Expenses
        expenses = MonthlyExpense.objects.filter(
            user=user,
            month__year=view_year, 
            month__month=view_month
        ).order_by('category', 'due_date', 'name')
        
        total_amount = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        total_paid = expenses.filter(is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
        total_pending = total_amount - total_paid

        # 3. Yearly Stats
        percentage_paid = 0
        if total_amount > 0:
            percentage_paid = (total_paid / total_amount) * 100

        # Global Yearly Stats (for dashboard top cards)
        current_year_expenses = MonthlyExpense.objects.filter(user=user, month__year=today.year)
        total_year_spent = current_year_expenses.filter(is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Active months count for average
        active_months = current_year_expenses.values('month').distinct().count() or 1
        average_monthly = total_year_spent / active_months

        # 4. History Summary
        history_summary = MonthlyExpense.objects.filter(user=user).values('month').annotate(
            total=Sum('amount'),
            paid=Sum('amount', filter=Q(is_paid=True)),
            count=Count('id')
        ).order_by('-month')

        # 5. Purchases
        purchases = Purchase.objects.filter(
            user=user,
            date__year=view_year, 
            date__month=view_month
        ).order_by('-date')
        
        total_purchase_amount = purchases.aggregate(Sum('amount'))['amount__sum'] or 0

        # 6. Navigation Helpers (Years & Months)
        years_query = MonthlyExpense.objects.filter(user=user).dates('month', 'year', order='DESC')
        available_years = sorted(list(set([d.year for d in years_query])), reverse=True)
        # Ensure navigation years are present
        target_years = {view_year, today.year, today.year - 1, today.year + 1}
        for y in target_years:
            if y not in available_years:
                available_years.append(y)
        available_years = sorted(list(set(available_years)), reverse=True)

        # Month Navigation Status
        year_status_map = FinanceReportService._get_year_status_map(view_year, user)
        months_navigation = []
        for m in range(1, 13):
            stat = year_status_map.get(m)
            has_data = bool(stat)
            is_paid = False
            if stat:
                paid_amt = stat['paid'] or 0
                total_amt = stat['total'] or 0
                if total_amt > 0 and paid_amt >= total_amt:
                    is_paid = True
            
            months_navigation.append({
                'num': m,
                'date': date(view_year, m, 1),
                'has_data': has_data,
                'is_paid': is_paid,
                'is_today_month': (view_year == today.year and m == today.month)
            })

        # Splitting Expenses
        fixed_expenses = expenses.filter(cost_definition__isnull=False)
        variable_expenses = expenses.filter(cost_definition__isnull=True)

        return {
            'expenses': expenses, # Combined for backward compat or totals if needed
            'fixed_expenses': fixed_expenses,
            'variable_expenses': variable_expenses,
            'current_month': current_month_date,
            'prev_month': prev_month_date,
            'next_month': next_month_date,
            'total_amount': total_amount,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'total_year_spent': total_year_spent,
            'average_monthly': average_monthly,
            'history_summary': history_summary,
            'purchases': purchases,
            'total_purchase_amount': total_purchase_amount,
            'available_years': available_years,
            'months_navigation': months_navigation,
            'today': today,
        }

    @staticmethod
    def _get_year_status_map(year, user):
        year_stats = MonthlyExpense.objects.filter(user=user, month__year=year).values('month__month').annotate(
            total=Sum('amount'),
            paid=Sum('amount', filter=Q(is_paid=True)),
        )
        return {x['month__month']: x for x in year_stats}
