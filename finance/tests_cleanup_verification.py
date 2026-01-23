from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.models import User
from django.db import connection

class MercadoPagoCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

    def test_mercadopago_urls_removed(self):
        """Verify that Mercado Pago URLs are no longer accessible/resolvable"""
        # 1. Verify URL reverse lookup fails (as they should be removed from urls.py)
        with self.assertRaises(NoReverseMatch):
            reverse('mercadopago_dashboard')
        
        with self.assertRaises(NoReverseMatch):
            reverse('mercadopago_import')

    def test_finance_module_health(self):
        """Verify that main finance views still work"""
        urls_to_check = [
            'fixed_cost_list',
            'fixed_cost_definition_list',
            'asset_list',
            'provider_list',
        ]
        
        for url_name in urls_to_check:
            try:
                url = reverse(url_name)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"Failed accessing {url_name}")
            except NoReverseMatch:
                self.fail(f"URL {url_name} reversed to NoReverseMatch")

    def test_database_cleanup(self):
        """Verify that Mercado Pago table is gone"""
        # This checks if the table exists in the database
        table_name = 'finance_mercadopagosettlement'
        with connection.cursor() as cursor:
            # This query is database agnostic enough for SQLite/Postgres for simple table check
            # For SQLite specifically:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=%s;", [table_name])
            row = cursor.fetchone()
            self.assertIsNone(row, f"Table {table_name} should have been deleted")
