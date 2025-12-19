import pytest
from django.contrib.auth.models import User
from inventory.forms import ProductForm, IngredientForm, ProductionForm
from inventory.models import Category, Product, Ingredient

@pytest.mark.django_db
class TestProductForm:
    def test_product_form_valid(self):
        user = User.objects.create(username="prod_user")
        category = Category.objects.create(name="Test Category", user=user)
        data = {
            'sku': 'SKU-001',
            'name': 'Test Product',
            'category': category.id,
            'description': 'Description',
            'net_weight': '100.00',
            'unit_measure': 'g',
            'cost_price': '10.00',
            'sale_price': '20.00',
            'stock_quantity': '50'
        }
        form = ProductForm(data=data)
        assert form.is_valid(), f"Errors: {form.errors}"
        product = form.save(commit=False)
        assert product.sku == 'SKU-001'

    def test_product_form_missing_required(self):
        data = {'name': 'No SKU'}
        form = ProductForm(data=data)
        assert not form.is_valid()
        assert 'sku' in form.errors
        assert 'unit_measure' in form.errors

    def test_product_form_invalid_numeric(self):
        data = {'sku': 'SKU-002', 'cost_price': 'not-a-number'}
        form = ProductForm(data=data)
        assert not form.is_valid()
        assert 'cost_price' in form.errors

@pytest.mark.django_db
class TestIngredientForm:
    def test_ingredient_form_valid(self):
        data = {
            'name': 'Flour',
            'type': 'raw_material',
            'unit': 'kg',
            'cost_per_unit': '500.00',
            'stock_quantity': '100.00'
        }
        form = IngredientForm(data=data)
        assert form.is_valid()
        ing = form.save(commit=False)
        assert ing.name == 'Flour'

    def test_ingredient_form_invalid_choice(self):
        data = {
            'name': 'Bad Type',
            'type': 'invalid_type', # Not in choices
            'unit': 'kg'
        }
        form = IngredientForm(data=data)
        assert not form.is_valid()
        assert 'type' in form.errors

@pytest.mark.django_db
class TestProductionForm:
    def test_production_form_valid(self):
        user = User.objects.create(username="maker")
        product = Product.objects.create(sku="P-1", name="Prod", user=user)
        data = {
            'product': product.id,
            'quantity': '10'
        }
        form = ProductionForm(data=data)
        # Note: ProductionForm queryset for 'product' might be empty if not initialized with filtering in mind or if global queryset is used.
        # forms.py defines: product = forms.ModelChoiceField(queryset=Product.objects.all(), ...)
        # So it should work.
        assert form.is_valid()
        assert form.cleaned_data['quantity'] == 10

    def test_production_form_negative_quantity(self):
        user = User.objects.create(username="maker2")
        product = Product.objects.create(sku="P-2", name="Prod2", user=user)
        data = {
            'product': product.id,
            'quantity': '-5' # Violation of min_value=1
        }
        form = ProductionForm(data=data)
        assert not form.is_valid()
        assert 'quantity' in form.errors
