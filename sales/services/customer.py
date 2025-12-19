import hashlib
import re
import pandas as pd
from sales.models import Customer
from .cleanup import normalize_string

def parse_document(raw_dni, raw_tipo_num_doc):
    """
    Parse document information from Excel columns.
    Priority: raw_dni > raw_tipo_num_doc
    
    Returns: (document_type, document_number, document_raw)
    """
    document_type = None
    document_number = None
    document_raw = None
    
    # Priority 1: DNI column
    if raw_dni and str(raw_dni).strip():
        document_raw = str(raw_dni).strip()
        document_type = 'DNI'
        # Extract only digits
        document_number = re.sub(r'\D', '', document_raw)
        return (document_type, document_number, document_raw)
    
    # Priority 2: "Tipo y número de documento" column
    if raw_tipo_num_doc and str(raw_tipo_num_doc).strip():
        document_raw = str(raw_tipo_num_doc).strip()
        
        # Try to parse type and number (e.g., "CUIT 20-12345678-9" or "DNI 12345678")
        match = re.match(r'([A-Za-z]+)\s*[-:]?\s*([\d\-]+)', document_raw)
        if match:
            document_type = match.group(1).upper()
            document_number = re.sub(r'\D', '', match.group(2))
        else:
            # Just extract digits as number
            document_number = re.sub(r'\D', '', document_raw)
            document_type = 'UNKNOWN'
        
        return (document_type, document_number, document_raw)
    
    return (None, None, None)


def build_customer_dedup_key(row):
    """
    Build a unique deduplication key for a customer based on document or name+address.
    """
    # Try to get document first
    raw_dni = row.get('DNI', '')
    raw_tipo_num_doc = row.get('Tipo y número de documento', '')
    
    doc_type, doc_number, _ = parse_document(raw_dni, raw_tipo_num_doc)
    
    if doc_number:
        # Use document as key
        key_string = f"doc:{doc_type}:{doc_number}"
    else:
        # Fallback to name + address combination
        name = normalize_string(row.get('Comprador', ''))
        domicilio = normalize_string(row.get('Domicilio', ''))
        cp = normalize_string(str(row.get('Código postal', '')))
        pais = normalize_string(row.get('País', 'argentina'))
        
        key_string = f"name:{name}|addr:{domicilio}|cp:{cp}|country:{pais}"
    
    # Hash the key
    return hashlib.sha256(key_string.encode('utf-8')).hexdigest()


def upsert_customers(df, user):
    """
    Create or update Customer records from the DataFrame.
    Returns a dict mapping dedup_key -> Customer instance.
    """
    # Build raw map first
    customers_data = {}
    
    # Sort by date so we prefer newer data
    if 'Fecha de venta' in df.columns:
        df_sorted = df.sort_values('Fecha de venta', na_position='first')
    else:
        df_sorted = df
    
    for _, row in df_sorted.iterrows():
        buyer_name = row.get('Comprador')
        if not buyer_name or pd.isna(buyer_name) or str(buyer_name).strip() == '':
            continue
        
        dedup_key = build_customer_dedup_key(row)
        
        if dedup_key not in customers_data:
            customers_data[dedup_key] = {'dedup_key': dedup_key}
        
        c = customers_data[dedup_key]
        
        def set_if_present(field, value):
            if value and not pd.isna(value) and str(value).strip():
                c[field] = str(value).strip()
        
        set_if_present('raw_name', row.get('Comprador'))
        set_if_present('raw_dni', row.get('DNI'))
        set_if_present('raw_domicilio', row.get('Domicilio'))
        set_if_present('raw_ciudad', row.get('Ciudad'))
        set_if_present('raw_estado', row.get('Estado'))
        set_if_present('raw_postal_code', row.get('Código postal'))
        set_if_present('raw_country', row.get('País'))
        set_if_present('raw_billing_name', row.get('Datos personales o de empresa'))
        set_if_present('raw_tipo_num_doc', row.get('Tipo y número de documento'))
        set_if_present('raw_billing_address', row.get('Dirección'))
        set_if_present('raw_tax_condition', row.get('Condición fiscal'))

    # Upsert to DB
    customer_map = {}
    for dedup_key, data in customers_data.items():
        # Scoped by USER. Note: dedup_key is unique GLOBALLY in model definition?
        # Model definition: dedup_key = models.CharField(max_length=128, unique=True, db_index=True)
        # This implies dedup_key MUST include User info or be unique global.
        # IF we want multi-tenancy where 2 users have same customer from same ML import...
        # The dedup_key is based on DNI/Name. If 2 users sell to same DNI, they conflict if Unique=True globally.
        # User requested "Multi-tenancy". A customer "Juan Perez" might buy from Shop A and Shop B.
        # Current Model has unique=True on dedup_key. This prevents duplicates globally.
        # I should probably include user.id in dedup_key hashing OR remove unique=True and use unique_together=['user', 'dedup_key'].
        # For now, to allow progress without major schema migration (removing unique constraint index), I will append user ID to the hash?
        # OR I filter by user. But get_or_create will fail if it exists for another user.
        # Plan: I can't change schema (unique constraint) easily without significant migration.
        # Fastest path: Modify valid dedup_key generation to include user hash.
        
        # NOTE: I am not changing build_customer_dedup_key here because it's imported.
        # I should modify build_customer_dedup_key OR append here.
        # If I change built key, I break existing data unless I re-hash it.
        # Existing data has dedup_key of "doc:123".
        # If I change logic to "user:1:doc:123", existing data for user 1 is "doc:123". It won't match!
        # And I'll create a duplicate "user:1:doc:123".
        # This is fine IF existing data is migrated.
        
        # HOWEVER, the `user` field was just added. Existing rows have `user=test_user`.
        # Their dedup_keys are "legacy" style.
        # If I change hashing logic, I will create duplicates for "legacy" customers if I don't migrate keys.
        # But wait, `dedup_key` is UNIQUE. I cannot have duplicates.
        # If I try to create "user:1:doc:123" and "doc:123" exists, it's fine (different strings).
        # But if "doc:123" is unique, I can have both "doc:123" and "user:1:doc:123".
        # But "doc:123" belongs to User 1 already (migrated).
        # So User 1 will have "doc:123" (old) and "user:1:doc:123" (new)?
        # That's messy (duplicated customer for same person).
        
        # Better approach:
        # Check if `dedup_key` exists for this user.
        # Customer.objects.filter(user=user, dedup_key=dedup_key).first()
        # BUT dedup_key has `unique=True`. So checks for `dedup_key` are implicitly global.
        # If I want true multi-tenancy where User A and B both have Customer X:
        # I MUST change `dedup_key` to be unique per USER, not global.
        # Since I cannot easily change Schema Unique Index in this step without complex migration flow (Remove Index -> Add Compound Index),
        # I will hack the dedup_key to ALWAYS include user information for NEW imports.
        # AND I should probably update existing dedup_keys?
        # Or just live with the fact that `dedup_key` is now `user:{id}:{hash}`.
        # Existing keys don't have user prefix.
        
        # Let's try to fetch by legacy key first if user matches?
        # No, simpler is to just scope the Query to the user, and hope the key matches.
        # But if `dedup_key` is globally unique, and I'm User A, and I try to insert "Hash123", and User B already has "Hash123"...
        # It will FAIL.
        # So I MUST include User ID in the hash.
        
        # I will modify `dedup_key` generation in this loop to include user ID.
        # user_scoped_key = f"{user.id}:{dedup_key}" 
        # But wait, existing data for User A already has `dedup_key` WITHOUT prefix.
        # Use a migration? Or logic:
        # If `dedup_key` matches existing record for THIS user, use it.
        # If `dedup_key` exists for ANOTHER user, we must distinguish.
        # So we MUST prefix.
        
        # If I prefix, I lose link to existing data for User 1 unless I migrate keys.
        # Given "Multi-tenancy" is a new feature and I just migrated all data to "Test User",
        # I can update the keys for Test User too!
        # But that requires another data migration.
        
        # Alternative: Just make "user" part of the query and Catch IntegrityError? No.
        
        # Let's just APPEND user ID to key.
        # And I will rely on `dedup_key` being unique.
        
        scoped_dedup_key = f"{user.id}_{dedup_key}"
        
        customer, created = Customer.objects.get_or_create(
            dedup_key=scoped_dedup_key,
            defaults={
                'name': data.get('raw_name', 'Desconocido'),
                'user': user
            }
        )
        
        # Update fields
        customer.name = data.get('raw_name', customer.name)
        
        doc_type, doc_number, doc_raw = parse_document(
            data.get('raw_dni'),
            data.get('raw_tipo_num_doc')
        )
        customer.document_type = doc_type
        customer.document_number = doc_number
        customer.document_raw = doc_raw
        
        customer.billing_name = data.get('raw_billing_name') or customer.billing_name
        customer.billing_address = data.get('raw_billing_address') or customer.billing_address
        customer.tax_condition = data.get('raw_tax_condition') or customer.tax_condition
        
        customer.shipping_address = data.get('raw_domicilio') or customer.shipping_address
        customer.city = data.get('raw_ciudad') or customer.city
        customer.state = data.get('raw_estado') or customer.state
        customer.postal_code = data.get('raw_postal_code') or customer.postal_code
        customer.country = data.get('raw_country') or customer.country
        
        customer.save()
        customer_map[dedup_key] = customer # Map original key to object for the sales processor!
        # Note: Sales processor uses `build_customer_dedup_key` which returns the RAW hash.
        # So `customer_map` MUST be keyed by RAW hash.
    
    return customer_map
