import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User
from finance.models import Provider, Purchase, MonthlyExpense, Asset, AssetCategory, PurchaseCategory

from django.test import TestCase

class TestFinanceViews(TestCase):
    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = client
        self.client.force_login(self.user)
        self.provider = Provider.objects.create(name="Test Provider", user=self.user)
        self.category = PurchaseCategory.objects.create(name="Test Category", user=self.user)

    def test_purchase_create_view_valid(self):
        url = reverse('purchase_create')
        data = {
            'date': '2024-01-20',
            'code': 'TEST-001',
            'provider': self.provider.id,
            'category': self.category.id,
            'description': 'Valid Purchase',
            'amount': '1000.00'
        }
        response = self.client.post(url, data)
        # Should redirect on success
        assert response.status_code == 302
        assert Purchase.objects.filter(code='TEST-001').exists()

    def test_purchase_create_view_invalid(self):
        url = reverse('purchase_create')
        # Missing required fields
        data = {'amount': '100'} 
        response = self.client.post(url, data)
        # Should redirect back (referer) or to list, but NOT create object
        # The view redirects on error too, but with messages. We can check object count.
        assert Purchase.objects.count() == 0
        
    def test_variable_expense_create_valid(self):
        url = reverse('variable_expense_create')
        data = {
            'name': 'Variable Test',
            'amount': '500.00',
            'due_date': '2024-05-01',
            'description': 'Desc'
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        assert MonthlyExpense.objects.filter(name='Variable Test').exists()

    def test_variable_expense_create_invalid(self):
        url = reverse('variable_expense_create')
        data = {'name': ''} # Invalid
        response = self.client.post(url, data)
        # Should not create
        assert MonthlyExpense.objects.filter(name='').count() == 0

    def test_asset_create_valid(self):
        url = reverse('asset_create')
        data = {
            'name': 'New Laptop',
            'cost': '1500.00',
            'purchase_date': '2024-06-01',
            'location': 'Home',
            'new_category': 'Electronics' # Test inline creation
        }
        response = self.client.post(url, data)
        assert response.status_code == 302
        asset = Asset.objects.get(name='New Laptop')
        assert asset.cost == Decimal('1500.00')
        assert asset.category.name == 'Electronics'

    def test_asset_create_invalid(self):
        url = reverse('asset_create')
        data = {'name': 'Bad Asset', 'cost': 'not-money'}
        response = self.client.post(url, data)
        assert response.status_code == 302 # Redirects on error
        assert not Asset.objects.filter(name='Bad Asset').exists()

    def test_login_required(self):
        self.client.logout()
        url = reverse('purchase_create')
        response = self.client.post(url, {})
        # Use Django's built-in assertion for redirects
        # Assuming defaults, but better to use settings if accessible, or standard logic.
        from django.conf import settings
        expected_url = f"{settings.LOGIN_URL}?next={url}"
        self.assertRedirects(response, expected_url)
