import pytest
from unittest.mock import MagicMock
import pandas as pd
from django.contrib.auth.models import User
from sales.services.importer import process_sales_file
from sales.models import Sale, Customer, SaleItem
from inventory.models import Product

@pytest.mark.django_db
class TestSalesImporter:
    def setup_method(self):
        self.user = User.objects.create(username="sales_tester")
        self.product = Product.objects.create(
            sku="SKU-TEST", name="Test Product", user=self.user, stock_quantity=100
        )

    def test_importer_valid_sale_deducts_stock(self):
        # Create a minimal DataFrame mimicking the excel structure
        data = {
            '# de venta': ['10001'],
            'Fecha de venta': [pd.Timestamp.now()],
            'Estado del pedido': ['Pagado'],
            'Comprador': ['Juan Perez'],
            'DNI': ['12345678'],
            'Domicilio': ['Calle Falsa 123'],
            'SKU': ['SKU-TEST'],
            'Unidades': [2],
            'Título de la publicación': ['Test Product Title'],
            'Precio unitario de venta de la publicación (ARS)': [500],
            'Ingresos por productos (ARS)': [1000]
        }
        df = pd.DataFrame(data)
        
        # Mock file object isn't needed if we patch pd.read_excel, 
        # but process_sales_file calls read_excel.
        # Let's mock pd.read_excel to return our DF.
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pandas.read_excel", lambda *args, **kwargs: df)
            
            # Call service (passing dummy file)
            stats = process_sales_file(MagicMock(), self.user)
            
        assert stats['new_sales'] == 1
        assert stats['errors'] == 0
        
        # Verify Sale created
        sale = Sale.objects.get(order_id='10001')
        assert sale.user == self.user
        assert sale.total > 0
        
        # Verify Customer created
        customer = Customer.objects.get(document_raw='12345678') # Logic uses DNI col for dedup/doc
        assert customer.name == 'Juan Perez'
        
        # Verify Stock Deduction (The Wall/E2E Critical Flow)
        self.product.refresh_from_db()
        assert self.product.stock_quantity == 98 # 100 - 2

    def test_importer_unknown_sku(self):
        data = {
            '# de venta': ['10002'],
            'Comprador': ['Maria'],
            'SKU': ['UNKNOWN-SKU'],
            'Unidades': [1],
            'Título de la publicación': ['Mystery Prod']
        }
        df = pd.DataFrame(data)
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pandas.read_excel", lambda *args, **kwargs: df)
            stats = process_sales_file(MagicMock(), self.user)
            
        assert stats['new_sales'] == 1
        assert len(stats['products_not_found']) > 0
        assert 'UNKNOWN-SKU' in stats['products_not_found'][0]
