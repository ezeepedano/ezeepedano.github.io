
import pandas as pd
import io
import os
import django
from django.conf import settings

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

from sales.services.importers.tiendanube import TiendaNubeImporter
from django.contrib.auth.models import User

# Mocking a user
try:
    user = User.objects.first()
except:
    user = None

filename = 'ventas-d00115c7-5b32-4e86-8f60-96e49d5aa024.csv'

print(f"--- Analyzing {filename} ---")

with open(filename, 'rb') as f:
    importer = TiendaNubeImporter(user)
    
    # We will manually do what process_file does to inspect the df
    content_bytes = f.read()
    
    # We know it's likely latin-1 from previous step
    content_str = content_bytes.decode('latin-1')
    
    df = pd.read_csv(io.StringIO(content_str), sep=';', engine='python')
    print("DataFrame Info:")
    print(df.info())
    
    # Iterate to find the "bad" row
    for index, row in df.iterrows():
        # Check a suspicious field
        addr = row.get('Dirección')
        
        # We suspect 'nan' string is surviving
        if str(addr).lower() == 'nan':
            print(f"\n--- FOUND PROPLEMATIC ROW Index: {index} ---")
            print(f"Dirección raw repr: {repr(addr)}")
            print(f"Dirección type: {type(addr)}")
            cleaned = importer._clean_str(addr)
            print(f"Cleaned address: '{cleaned}' (Length: {len(cleaned)})")
            
            # Check if cleaned is still 'nan'
            if cleaned.lower() == 'nan':
                 print("!!! FAIL: _clean_str returning 'nan' !!!")
            
            # Check other fields
            print(f"Nombre: {repr(row.get('Nombre del comprador'))}")
            print(f"Clean Nombre: '{importer._clean_str(row.get('Nombre del comprador'))}'")
            break
            
    print("\n--- Script End ---")
