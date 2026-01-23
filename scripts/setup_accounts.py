import os
import django
import sys
from decimal import Decimal
from django.utils import timezone

sys.path.append('c:\\Users\\Giuliana\\OneDrive - alumnos.iua.edu.ar\\JKGE 2025\\ERP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User
from finance.models import Account

def setup_accounts():
    print("=== SETUP DEFAULT ACCOUNTS ===")
    
    users = User.objects.all()
    
    default_accounts = [
        {'name': 'Caja Chica', 'type': 'CASH', 'opening_balance': 0},
        {'name': 'Banco Santander', 'type': 'BANK', 'opening_balance': 0},
        {'name': 'Mercado Pago', 'type': 'WALLET', 'opening_balance': 0},
    ]
    
    for user in users:
        print(f" Processing user: {user.username}")
        for acc_data in default_accounts:
            account, created = Account.objects.get_or_create(
                user=user,
                name=acc_data['name'],
                defaults={
                    'type': acc_data['type'],
                    'opening_balance': Decimal(str(acc_data['opening_balance'])),
                    'opening_date': timezone.datetime(2026, 1, 1).date(),
                    'is_active': True
                }
            )
            if created:
                print(f"  [+] Created {account.name}")
            else:
                print(f"  [.] Exists {account.name}")
                
    print("=== SETUP COMPLETE ===")

if __name__ == '__main__':
    setup_accounts()
