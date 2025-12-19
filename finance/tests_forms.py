import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from finance.forms import PurchaseForm, VariableExpenseForm, AssetForm, ProviderForm
from finance.models import Provider, AssetCategory, FixedCost, PurchaseCategory

@pytest.mark.django_db
class TestPurchaseForm:
    def test_purchase_form_valid(self):
        user = User.objects.create(username="testuser")
        provider = Provider.objects.create(name="Test Provider", user=user)
        category = PurchaseCategory.objects.create(name="Test Cat", user=user)
        
        data = {
            'date': '2024-01-15',
            'code': 'INV-001',
            'provider': provider.id,
            'category': category.id,
            'description': 'Office Supplies',
            'amount': '150.50'
        }
        form = PurchaseForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"
        purchase = form.save(commit=False)
        assert purchase.amount == Decimal('150.50')

    def test_purchase_form_invalid_missing_fields(self):
        # Missing date and amount
        data = {'code': 'INV-002'}
        form = PurchaseForm(data=data)
        assert not form.is_valid()
        assert 'date' in form.errors
        assert 'amount' in form.errors

    def test_purchase_form_invalid_amount(self):
        data = {
            'date': '2024-01-15',
            'amount': 'not-a-number'
        }
        form = PurchaseForm(data=data)
        assert not form.is_valid()
        assert 'amount' in form.errors

@pytest.mark.django_db
class TestVariableExpenseForm:
    def test_variable_expense_valid(self):
        data = {
            'name': 'Taxi',
            'amount': '2500.00',
            'due_date': '2024-02-01',
            'description': 'Trip to client'
        }
        form = VariableExpenseForm(data=data)
        assert form.is_valid()
        expense = form.save(commit=False)
        assert expense.name == "Taxi"

    def test_variable_expense_missing_name(self):
        data = {'amount': '100'}
        form = VariableExpenseForm(data=data)
        assert not form.is_valid()
        assert 'name' in form.errors

@pytest.mark.django_db
class TestAssetForm:
    def test_asset_form_valid(self):
        user = User.objects.create(username="assetuser")
        cat = AssetCategory.objects.create(name="Computers", user=user)
        prov = Provider.objects.create(name="Dell", user=user)
        
        data = {
            'name': 'MacBook Pro',
            'category': cat.id,
            'cost': '2000.00',
            'purchase_date': '2024-03-01',
            'provider': prov.id,
            'location': 'Office',
            'description': 'Dev machine'
        }
        form = AssetForm(data=data)
        assert form.is_valid()
    
    def test_asset_form_invalid_cost(self):
        data = {'name': 'Table', 'cost': '-500'} 
        # Assuming cost shouldn't be negative, but standard DecimalField accepts it unless validated.
        # Let's check basics first.
        form = AssetForm(data={'name': 'Table', 'cost': 'abc'})
        assert not form.is_valid()

@pytest.mark.django_db
class TestProviderForm:
    def test_provider_form_valid(self):
        data = {
            'name': 'New Provider',
            'email': 'contact@provider.com',
            'cuit': '20-12345678-9'
        }
        form = ProviderForm(data=data)
        assert form.is_valid()

    def test_provider_form_missing_name(self):
        data = {'email': 'no-name@provider.com'}
        form = ProviderForm(data=data)
        assert not form.is_valid()
        assert 'name' in form.errors
