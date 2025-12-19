import pandas as pd
from django.utils import timezone
import unicodedata
import re
import warnings

def normalize_string(value):
    """
    Normalize a string for deduplication:
    - Trim whitespace
    - Lowercase
    - Replace multiple spaces with single space
    - Remove accents
    """
    if not value or not isinstance(value, str):
        return ''
    
    # Trim and lowercase
    value = value.strip().lower()
    
    # Replace multiple spaces with single space
    value = re.sub(r'\s+', ' ', value)
    
    # Remove accents
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(c for c in value if not unicodedata.combining(c))
    
    return value

def parse_spanish_date(x):
    """Convert Spanish date strings to parseable format."""
    if not isinstance(x, str):
        return x
    
    months = {
        'enero': 'January', 'febrero': 'February', 'marzo': 'March', 'abril': 'April',
        'mayo': 'May', 'junio': 'June', 'julio': 'July', 'agosto': 'August',
        'septiembre': 'September', 'octubre': 'October', 'noviembre': 'November', 'diciembre': 'December'
    }
    
    x = x.lower().strip()
    for es, en in months.items():
        if es in x:
            x = x.replace(es, en)
            break
    
    x = x.replace(' de ', ' ').replace(' hs.', '')
    return x

def clean_sales_dataframe(df):
    """Clean and normalize DataFrame columns."""
    date_cols = ['Fecha de venta', 'Fecha en camino', 'Fecha entregado']
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(parse_spanish_date)
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                df[col] = df[col].apply(lambda x: timezone.make_aware(x) if pd.notnull(x) and timezone.is_naive(x) else x)

    numeric_cols = [
        'Ingresos por productos (ARS)', 
        'Cargo por venta e impuestos (ARS)', 
        'Cargo por venta',
        'Costo fijo',
        'Costo por ofrecer cuotas',
        'Impuestos',
        'Descuentos',
        'Ingresos por envío (ARS)', 
        'Costos de envío (ARS)', 
        'Costo de envío basado en medidas y peso declarados',
        'Cargo por diferencias en medidas y peso del paquete',
        'Anulaciones y reembolsos (ARS)', 
        'Total (ARS)',
        'Precio unitario de venta de la publicación (ARS)',
        'Unidades'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    rename_map = {
        'Estado': 'Estado del pedido',
        'Estado.1': 'Provincia'
    }
    df = df.rename(columns=rename_map)
    return df
