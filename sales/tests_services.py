from django.test import TestCase
from .services.cleanup import normalize_string, parse_spanish_date

class SalesCleanupTests(TestCase):
    def test_normalize_string(self):
        self.assertEqual(normalize_string("  HOLA   Mundo  "), "hola mundo")
        self.assertEqual(normalize_string("Camión"), "camion")
        self.assertEqual(normalize_string(""), "")
        self.assertEqual(normalize_string(None), "")

    def test_parse_spanish_date(self):
        self.assertEqual(parse_spanish_date("10 de Enero de 2024"), "10 January 2024")
        self.assertEqual(parse_spanish_date("5 de Marzo"), "5 March")
        self.assertEqual(parse_spanish_date("Diciembre"), "December")
        # Ensure it handles mixed case
        self.assertEqual(parse_spanish_date("10 DE AGOSTO"), "10 August")
