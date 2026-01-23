from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from sales.models import Customer

class CustomerCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        self.url = reverse('customer_create')

    def test_customer_create_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sales/customers/form.html')

    def test_customer_create_success(self):
        data = {
            'name': 'Test Customer',
            'document_number': '12345678901',
            'billing_name': 'Test Customer',
            'billing_address': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
        }
        response = self.client.post(self.url, data)
        if response.status_code != 302:
            print(f"Form Errors: {response.context['form'].errors}")
        self.assertEqual(response.status_code, 302) # Redirects
        self.assertTrue(Customer.objects.filter(name='Test Customer').exists())

    def test_customer_create_save_and_sale(self):
        data = {
            'name': 'Sale Customer',
            'document_number': '98765432109',
            'save_and_sale': '1'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='Sale Customer')
        expected_url = f"{reverse('sale_create')}?customer={customer.id}"
        self.assertRedirects(response, expected_url)
