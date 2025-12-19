import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.test import Client
from django.core import mail
from django.contrib.auth.models import User

def test_web_reset():
    print("--- Testing Web Password Reset Flow ---")
    target_email = 'alexanderbozzetto@gmail.com'
    
    # Ensure user exists
    if not User.objects.filter(email=target_email).exists():
        print(f"User {target_email} does not exist. Creating temporarily or failing.")
        # We assume it exists based on previous turn.
        print("❌ User not found in DB! Web flow will fail silently.")
        return

    c = Client()
    # 1. GET request
    resp = c.get('/password-reset/')
    if resp.status_code != 200:
        print(f"❌ Error accessing page: {resp.status_code}")
        return
    print("✅ GET /password-reset/ OK")

    # 2. POST request
    print(f"POSTing reset for {target_email}...")
    resp = c.post('/password-reset/', {'email': target_email}, follow=True)
    
    if resp.status_code == 200:
        # Check if we landed on 'password_reset_done'
        # Django's redirect usually lands on the done page.
        # We can check the chain or the template used.
        templates = [t.name for t in resp.templates]
        print(f"Templates used: {templates}")
        if 'users/password_reset_done.html' in templates:
            print("✅ Web flow redirected to DONE page.")
        else:
             print("⚠️ Did not redirect to expected DONE page (check templates).")
    else:
        print(f"❌ Response Status: {resp.status_code}")

    # 3. Check Mail Outbox (This only works if using Console/Memory backend or if we can intercept mock)
    # BUT, we are running in a script process. If settings are using Real SMTP, 'mail.outbox' won't catch it unless we mock it.
    # However, if we configured SMTP, it *should* send real email.
    # We can't check 'mail.outbox' effectively if using SMTP backend in live settings.
    # BUT, we can inspect output if any print debugging was added, OR rely on user checking inbox.
    
    # To really verify "why it fails", logging is better. 
    # But let's see if the VIEW returns success code first.

if __name__ == '__main__':
    test_web_reset()
