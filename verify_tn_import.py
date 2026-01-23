import os
import django
import io
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_erp.settings")
django.setup()

from sales.services.importers.tiendanube import TiendaNubeImporter
from django.contrib.auth.models import User
from sales.models import Sale, Customer

# 1. Setup Dummy Data
user, _ = User.objects.get_or_create(username='test_admin', defaults={'email': 'admin@example.com'})

# Sample CSV Content (Latin-1 encoded style as seen in analysis)
csv_content = """Número de orden;Email;Fecha;Estado de la orden;Estado del pago;Estado del envío;Moneda;Subtotal de productos;Descuento;Costo de envío;Total;Nombre del comprador;DNI / CUIT;Teléfono;Nombre para el envío;Teléfono para el envío;Dirección;Número;Piso;Localidad;Ciudad;Código postal;Provincia o estado;País;Medio de envío;Medio de pago;Cupón de descuento;Notas del comprador;Notas del vendedor;Fecha de pago;Fecha de envío;Nombre del producto;Precio del producto;Cantidad del producto;SKU;Canal;Código de tracking del envío;Identificador de la transacción en el medio de pago;Identificador de la orden;Producto Físico;Persona que registró la venta;Sucursal de venta;Vendedor;Fecha y hora de cancelación;Motivo de cancelación
12345;test@example.com;20/12/2025 10:00:00;Abierta;Recibido;Enviado;ARS;1000,00;0,00;500,00;1500,00;Juan Perez;12345678;+5491112345678;Juan Perez;;Av. Test;123;;;CABA;1000;CABA;Argentina;EnvioPropio;MP;;;;20/12/2025;20/12/2025;Producto Test;1000,00;1;TEST-SKU;Web;="TRACK123";TRANS123;ORD123;Sí;;;;;
"""

print("Running Tienda Nube Import Verification...")

file_obj = io.BytesIO(csv_content.encode('latin-1'))
importer = TiendaNubeImporter(user)

# 2. Process
stats = importer.process_file(file_obj)

print("Stats:", stats)

# 3. Verify
sale = Sale.objects.filter(order_id='12345').first()
if sale:
    print(f"SUCCESS: Sale created. Order ID: {sale.order_id}")
    print(f"  Total: {sale.total}")
    print(f"  Customer: {sale.customer.name} (Doc: {sale.customer.document_number})")
    print(f"  Date: {sale.date}")
    print(f"  Status: {sale.status}")
    print(f"  Channel: {sale.channel}")
    
    items = sale.items.all()
    print(f"  Items ({items.count()}):")
    for item in items:
        print(f"    - {item.product_title} (Qty: {item.quantity})")
else:
    print("FAILURE: Sale not created.")

# Cleanup
if sale:
    sale.delete()
    # verify cleanup
    print("Cleanup complete.")
