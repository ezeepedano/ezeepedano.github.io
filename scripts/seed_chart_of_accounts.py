import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from accounting.models import Account

def seed_accounts():
    """
    Creates a standard Chart of Accounts for an SME (Pyme).
    """
    print("Seeding/Updating Chart of Accounts...")
    
    # We remove the global check so we can add new accounts incrementally.
    # if Account.objects.exists(): ...

    accounts = [
        # ACTIVOS
        {'code': '1.0.00', 'name': 'ACTIVO', 'type': 'ASSET', 'parent': None},
        {'code': '1.1.00', 'name': 'Activo Corriente', 'type': 'ASSET', 'parent': '1.0.00'},
        {'code': '1.1.01', 'name': 'Caja y Bancos', 'type': 'ASSET', 'parent': '1.1.00'},
        {'code': '1.1.01.01', 'name': 'Caja Principal', 'type': 'ASSET', 'parent': '1.1.01', 'reconcilable': True},
        {'code': '1.1.01.02', 'name': 'Banco Galicia', 'type': 'ASSET', 'parent': '1.1.01', 'reconcilable': True},
        {'code': '1.1.01.03', 'name': 'Mercado Pago', 'type': 'ASSET', 'parent': '1.1.01', 'reconcilable': True},
        {'code': '1.1.02', 'name': 'Créditos por Ventas', 'type': 'ASSET', 'parent': '1.1.00'},
        {'code': '1.1.02.01', 'name': 'Deudores por Ventas', 'type': 'ASSET', 'parent': '1.1.02', 'reconcilable': True},
        {'code': '1.1.03', 'name': 'Bienes de Cambio', 'type': 'ASSET', 'parent': '1.1.00'},
        {'code': '1.1.03.01', 'name': 'Mercaderías de Reventa', 'type': 'ASSET', 'parent': '1.1.03'},
        
        # PASIVOS
        {'code': '2.0.00', 'name': 'PASIVO', 'type': 'LIABILITY', 'parent': None},
        {'code': '2.1.00', 'name': 'Pasivo Corriente', 'type': 'LIABILITY', 'parent': '2.0.00'},
        {'code': '2.1.01', 'name': 'Deudas Comerciales', 'type': 'LIABILITY', 'parent': '2.1.00'},
        {'code': '2.1.01.01', 'name': 'Proveedores', 'type': 'LIABILITY', 'parent': '2.1.01', 'reconcilable': True},
        {'code': '2.1.02', 'name': 'Deudas Fiscales', 'type': 'LIABILITY', 'parent': '2.1.00'},
        {'code': '2.1.02.01', 'name': 'IVA Débito Fiscal', 'type': 'LIABILITY', 'parent': '2.1.02'},
        
        # PATRIMONIO
        {'code': '3.0.00', 'name': 'PATRIMONIO NETO', 'type': 'EQUITY', 'parent': None},
        {'code': '3.1.00', 'name': 'Capital Social', 'type': 'EQUITY', 'parent': '3.0.00'},
        
        # INGRESOS
        {'code': '4.0.00', 'name': 'INGRESOS', 'type': 'REVENUE', 'parent': None},
        {'code': '4.1.00', 'name': 'Ventas', 'type': 'REVENUE', 'parent': '4.0.00'},
        {'code': '4.1.01', 'name': 'Ventas de Mercaderías', 'type': 'REVENUE', 'parent': '4.1.00'},
        
        # EGRESOS
        {'code': '5.0.00', 'name': 'EGRESOS', 'type': 'EXPENSE', 'parent': None},
        {'code': '5.1.00', 'name': 'Costos Operativos', 'type': 'EXPENSE', 'parent': '5.0.00'},
        {'code': '5.1.01', 'name': 'Costo de Mercaderías Vendidas', 'type': 'EXPENSE', 'parent': '5.1.00'},
        {'code': '5.2.00', 'name': 'Gastos Administrativos', 'type': 'EXPENSE', 'parent': '5.0.00'},
        {'code': '5.2.01', 'name': 'Alquileres', 'type': 'EXPENSE', 'parent': '5.2.00'},
        {'code': '5.2.02', 'name': 'Servicios (Luz, Gas, Internet)', 'type': 'EXPENSE', 'parent': '5.2.00'},
        {'code': '5.2.99', 'name': 'Gastos Varios', 'type': 'EXPENSE', 'parent': '5.2.00'},
    ]

    print("Seeding Chart of Accounts...")
    
    # Needs 2 passes or careful ordering for parents. 
    # Since list is ordered hierarchically, we can do it in one pass if we lookup parent by code.
    
    created_count = 0
    for data in accounts:
        parent = None
        if data['parent']:
            try:
                parent = Account.objects.get(code=data['parent'])
            except Account.DoesNotExist:
                print(f"Error: Parent {data['parent']} not found for {data['code']}")
                continue
        
        obj, created = Account.objects.get_or_create(
            code=data['code'],
            defaults={
                'name': data['name'],
                'type': data['type'],
                'parent': parent,
                'is_reconcilable': data.get('reconcilable', False)
            }
        )
        if created:
            created_count += 1
            print(f"Created: {data['code']} - {data['name']}")
        else:
             # Optional: Update existing if needed, for now just skip
             pass

    print(f"Done. Created {created_count} new accounts.")

if __name__ == '__main__':
    seed_accounts()
