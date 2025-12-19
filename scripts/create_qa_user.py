import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.contrib.auth.models import User

username = 'qa_user'
password = 'qa_password_123'
email = 'qa@example.com'

if not User.objects.filter(username=username).exists():
    User.objects.create_user(username=username, password=password, email=email)
    print(f"User '{username}' created successfully.")
else:
    print(f"User '{username}' already exists.")
