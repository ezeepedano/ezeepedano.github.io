from django.test import TestCase, Client
from django.urls import reverse

class PasswordResetTest(TestCase):
    def test_password_reset_page_status(self):
        client = Client()
        url = reverse('password_reset')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
