from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from finance.models import Account, CashMovement
from sales.models import Sale
from finance.models import Purchase, Provider

class FinanceDashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')
        
        # Setup Accounts
        self.bank = Account.objects.create(user=self.user, name='Banco Test', type='BANK', opening_balance=Decimal('1000'))
        self.cash = Account.objects.create(user=self.user, name='Caja Test', type='CASH', opening_balance=Decimal('500'))
        
        # Setup Movements
        CashMovement.objects.create(user=self.user, account=self.bank, amount=Decimal('200'), type='IN', date=timezone.now())
        CashMovement.objects.create(user=self.user, account=self.cash, amount=Decimal('100'), type='OUT', date=timezone.now())
        
        # Setup Aging Data
        self.provider = Provider.objects.create(user=self.user, name='Prov Test')
        Purchase.objects.create(user=self.user, provider=self.provider, amount=Decimal('500'), date=timezone.now(), due_date=timezone.now(), payment_status='PENDING')
        Sale.objects.create(user=self.user, total=Decimal('1000'), date=timezone.now(), due_date=timezone.now(), payment_status='PENDING')

    def test_cashflow_dashboard(self):
        response = self.client.get('/finance/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Banco Test')
        # Balance check: Bank = 1000 + 200 = 1200. Cash = 500 - 100 = 400. Total = 1600.
        context_balance = response.context['total_balance']
        self.assertEqual(context_balance, Decimal('1600'))

    def test_aging_dashboard(self):
        response = self.client.get('/finance/aging/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cuentas Corrientes')
        self.assertEqual(response.context['total_receivables'], Decimal('1000'))
        self.assertEqual(response.context['total_payables'], Decimal('500'))

    def test_import_view_loads(self):
        response = self.client.get('/finance/import/')
        self.assertEqual(response.status_code, 200)
