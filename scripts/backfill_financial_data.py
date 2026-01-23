import os
import django
from decimal import Decimal
import datetime

import sys
sys.path.append('c:\\Users\\Giuliana\\OneDrive - alumnos.iua.edu.ar\\JKGE 2025\\ERP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from django.utils import timezone
from sales.models import Sale
from finance.models import Purchase

def backfill_financial_data():
    print("=== BACKFILL FINANCIAL DATA (OPTION A) ===")
    
    # 1. Backfill Sales
    # Strategy: Mark all existing sales as PAID, due_date = date, paid_amount = total
    print(" Updating Sales...")
    sales_qs = Sale.objects.exclude(status__icontains='cancel')
    count = 0
    for sale in sales_qs:
        updated = False
        if sale.payment_status != 'PAID':
            sale.payment_status = 'PAID'
            updated = True
        
        if sale.paid_amount != sale.total:
            sale.paid_amount = sale.total
            updated = True
            
        if not sale.due_date:
            # If date is datetime, take date.
            if isinstance(sale.date, datetime.datetime):
                sale.due_date = sale.date.date()
            else:
                sale.due_date = sale.date
            updated = True
            
        if updated:
            sale.save()
            count += 1
            
    print(f" [DONE] Updated {count} Sales to PAID status.")

    # 2. Backfill Purchases
    print(" Updating Purchases...")
    purchases_qs = Purchase.objects.all()
    p_count = 0
    for purchase in purchases_qs:
        updated = False
        # Map legacy 'is_paid' boolean if useful, else assume PAID as per Option A
        # If legacy is_paid=False, should we mark as PENDING?
        # User said "Mark them ALL as PAID (Option A)". Assuming this overrides legacy flag.
        # But if legacy is_paid is False, it might be truly unpaid.
        # Let's check if is_paid is False.
        
        if not purchase.is_paid:
            # If it was marked unpaid heavily, maybe keep it?
            # User said "Mark them all as PAID". I will follow instruction.
            pass

        if purchase.payment_status != 'PAID':
            purchase.payment_status = 'PAID'
            updated = True
        
        if purchase.paid_amount != purchase.amount:
            purchase.paid_amount = purchase.amount
            updated = True
            
        if not purchase.due_date:
            # Purchases have 'date' usually? Purchase model schema:
            # date = models.DateField()
            purchase.due_date = purchase.date
            updated = True
            
        if updated:
            purchase.save()
            p_count += 1
            
    print(f" [DONE] Updated {p_count} Purchases to PAID status.")
    print("=== BACKFILL COMPLETE ===")

if __name__ == '__main__':
    backfill_financial_data()
