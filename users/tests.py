from django.test import TestCase, Client
from django.contrib.auth.models import User
from inventory.models import Product, Ingredient

class MultiTenancyIsolationTests(TestCase):
    def setUp(self):
        # Create User A
        self.user_a = User.objects.create_user(username='user_a', password='password123')
        self.client_a = Client()
        self.client_a.login(username='user_a', password='password123')
        
        # Create User B
        self.user_b = User.objects.create_user(username='user_b', password='password123')
        self.client_b = Client()
        self.client_b.login(username='user_b', password='password123')
        
        # Create Data for User A
        self.product_a = Product.objects.create(user=self.user_a, sku='SKU_A', name='Product A', unit_measure='u')
        self.ingredient_a = Ingredient.objects.create(user=self.user_a, name='Ingredient A', unit='kg', cost_per_unit=10)
        
        # Create Data for User B
        self.product_b = Product.objects.create(user=self.user_b, sku='SKU_B', name='Product B', unit_measure='u')
        self.ingredient_b = Ingredient.objects.create(user=self.user_b, name='Ingredient B', unit='kg', cost_per_unit=20)

    def test_user_a_only_sees_own_products(self):
        # User A requests product list
        response = self.client_a.get('/inventory/products/') # Verify URL path in urls.py
        self.assertEqual(response.status_code, 200)
        
        # Should see Product A
        self.assertContains(response, 'Product A')
        # Should NOT see Product B
        self.assertNotContains(response, 'Product B')

    def test_user_b_only_sees_own_products(self):
        # User B requests product list
        response = self.client_b.get('/inventory/products/')
        self.assertEqual(response.status_code, 200)
        
        # Should see Product B
        self.assertContains(response, 'Product B')
        # Should NOT see Product A
        self.assertNotContains(response, 'Product A')

    def test_cross_user_access_denied_detail_view(self):
        # User A tries to view Product B detail
        # Provide PK of Product B
        response = self.client_a.get(f'/inventory/product/{self.product_b.pk}/edit/') # Assuming edit URL
        # Should be 404 (Not Found) because filter excludes it, OR 403.
        # Views use get_object_or_404(Product.objects.filter(user=request.user), pk=pk)
        # So it should be 404.
        self.assertEqual(response.status_code, 404)
