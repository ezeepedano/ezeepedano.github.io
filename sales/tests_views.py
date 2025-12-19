from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from sales.models import Sale, Customer

class TestSalesViews(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sales_view_user", password="password")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(name="Customer A", user=self.user, dedup_key="key1")
        self.sale = Sale.objects.create(
            user=self.user, order_id="ORDER-1", customer=self.customer, total=1000, date="2024-01-01 10:00:00"
        )

    def test_dashboard_access(self):
        url = reverse('sales_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ORDER-1")

    def test_upload_view_access(self):
        url = reverse('upload_sales')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_customer_list_access(self):
        url = reverse('customer_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer A")

    def test_login_required(self):
        self.client.logout()
        url = reverse('sales_dashboard')
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)
        # 302 redirect expected
        self.assertEqual(response.status_code, 302)
