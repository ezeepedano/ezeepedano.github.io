import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User

try:
    if not User.objects.filter(username='testadmin').exists():
        User.objects.create_superuser('testadmin', 'test@example.com', 'password123')
        print("User 'testadmin' created successfully.")
    else:
        u = User.objects.get(username='testadmin')
        u.set_password('password123')
        u.save()
        print("User 'testadmin' already exists. Password reset.")
except Exception as e:
    print(f"Error: {e}")
