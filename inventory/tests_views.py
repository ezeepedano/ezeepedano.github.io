from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from inventory.models import Category, Product, Ingredient, ProductionOrder

@override_settings(ALLOWED_HOSTS=['testserver', '127.0.0.1'])
class TestInventoryViews(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="inv_user", password="password")
        self.client.force_login(self.user)
        self.category = Category.objects.create(name="Raw Materials", user=self.user)

    def test_product_create_view_valid(self):
        url = reverse('product_create')
        data = {
            'sku': 'PROD-001',
            'name': 'Widget A',
            'category': self.category.id,
            'description': 'A widget',
            'net_weight': '500',
            'unit_measure': 'g',
            'cost_price': '100',
            'sale_price': '200',
            'stock_quantity': '10'
        }
        response = self.client.post(url, data)
        if response.status_code == 200:
             form = response.context['form']
             # Fail with helpful message if form is invalid
             self.assertFalse(form.errors, f"Form Errors: {form.errors}")
        self.assertRedirects(response, reverse('product_list'))
        assert Product.objects.filter(sku='PROD-001').exists()

    def test_product_create_view_invalid(self):
        url = reverse('product_create')
        data = {'name': 'No SKU'} 
        response = self.client.post(url, data)
        assert response.status_code == 200 
        assert Product.objects.count() == 0

    def test_ingredient_create_view_valid(self):
        url = reverse('ingredient_create')
        data = {
            'name': 'Sugar',
            'type': 'raw_material',
            'unit': 'kg',
            'cost_per_unit': '120.50',
            'stock_quantity': '50'
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('ingredient_list'))
        assert Ingredient.objects.filter(name='Sugar').exists()

    def test_produce_product_view_valid(self):
        # Setup: Need a product AND a recipe (ProductionService requirement)
        product = Product.objects.create(
            sku="P-X", name="X", user=self.user, 
            net_weight=100, unit_measure='g', stock_quantity=10
        )
        ingredient = Ingredient.objects.create(
            name="Raw Material 1", type='raw_material', 
            user=self.user, cost_per_unit=10, stock_quantity=100
        )
        from inventory.models import Recipe
        Recipe.objects.create(
            product=product, ingredient=ingredient, quantity=2, user=self.user
        )
        
        url = reverse('produce_product')
        data = {
            'product': product.id,
            'quantity': 5
        }
        response = self.client.post(url, data)
        # View redirects to itself ('produce_product') on success
        self.assertRedirects(response, reverse('produce_product'))

    def test_login_required(self):
        self.client.logout()
        url = reverse('product_create')
        response = self.client.post(url, {})
        from django.conf import settings
        from django.shortcuts import resolve_url
        login_url = resolve_url(settings.LOGIN_URL)
        expected_url = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_url)
