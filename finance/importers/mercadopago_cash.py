import pandas as pd
from decimal import Decimal
from django.utils import timezone
from finance.models import CashMovement, Account

class MercadoPagoCashImporter:
    def __init__(self, user):
        self.user = user
        # Find MP Account
        self.account = Account.objects.filter(user=user, type='WALLET', name__icontains='Mercado').first()
        if not self.account:
            # Fallback or error? Let's create one if missing or error.
            self.account, _ = Account.objects.get_or_create(
                user=user, 
                name='Mercado Pago', 
                defaults={'type':'WALLET'}
            )
            
    def process_file(self, file_obj):
        try:
            # Read CSV (settlement format usually comma or semi-colon)
            # We try comma first
            try:
                df = pd.read_csv(file_obj)
            except:
                file_obj.seek(0)
                df = pd.read_csv(file_obj, sep=';')
                
            stats = {'created': 0, 'duplicates': 0, 'errors': 0}
            
            # Expected columns in settlement report:
            # 'TRANSACTION_DATE', 'SOURCE_ID' (internal?), 'EXTERNAL_REFERENCE' (our ID), 
            # 'DESCRIPTION', 'NET_CREDIT_AMOUNT' (final amount)
            # Or Spanish: 'FECHA', 'REFERENCIA', 'DESCRIPCION', 'IMPORTE'
            
            # Let's map dynamically based on typical MP columns
            # MP often uses: 'date_created', 'operation_id', 'description', 'net_received_amount' in some reports.
            # Or standard Settlement Report:
            # begin_date, end_date, ... detail rows?
            
            # If the user provided file 'settlement-...' it's likely the "Reporte de Liquidaciones" or "Todas las actividades".
            # "Todas las actividades" (Activities) is better for cash flow detail.
            # "Settlement" (Liquidaciones) aggregates by payout.
            
            # Assuming ACTIVITY report for granular detail based on "movements":
            # Cols: 'Date', 'Source ID' (op id), 'Description', 'Net Amount' ...
            
            # Let's normalize columns to lower
            df.columns = df.columns.str.lower()
            
            # Identification logic
            col_id = next((c for c in df.columns if 'operation' in c or 'operación' in c or 'source_id' in c), None)
            col_date = next((c for c in df.columns if 'date' in c or 'fecha' in c), None)
            col_amount = next((c for c in df.columns if 'net' in c or 'neto' in c or 'amount' in c or 'importe' in c), None)
            col_desc = next((c for c in df.columns if 'desc' in c), None)
            
            if not col_id or not col_amount:
                return {'error': "Could not identify ID or Amount columns. Please check CSV format."}

            for _, row in df.iterrows():
                try:
                    ext_id = str(row[col_id])
                    
                    # Deduplication
                    if CashMovement.objects.filter(external_id=ext_id).exists():
                        stats['duplicates'] += 1
                        continue
                        
                    # Parse Amount
                    amount_val = row[col_amount]
                    amount_dec = Decimal(str(amount_val))
                    
                    if amount_dec == 0:
                        continue
                        
                    direction = 'IN' if amount_dec > 0 else 'OUT'
                    abs_amount = abs(amount_dec)
                    
                    # Parse Date
                    date_val = pd.to_datetime(row[col_date])
                    
                    # Category logic
                    desc = str(row[col_desc]) if col_desc else ''
                    desc_lower = desc.lower()
                    category = 'OTHER'
                    
                    if 'cobro' in desc_lower or 'boleta' in desc_lower:
                        category = 'SALE'
                    elif 'transfer' in desc_lower or 'envío' in desc_lower or 'ingreso de dinero' in desc_lower:
                        category = 'TRANSFER'
                    elif 'compra' in desc_lower:
                        category = 'PURCHASE'
                    elif any(k in desc_lower for k in ['impuesto', 'retenc', 'iibb', 'sello', 'afip']):
                        category = 'TAX'
                    elif any(k in desc_lower for k in ['comisi', 'cargo', 'tarifa', 'costo']):
                        category = 'EXPENSE'
                    elif any(k in desc_lower for k in ['devoluci', 'disputa', 'contracargo', 'ajuste']):
                        category = 'ADJUSTMENT'
                    
                    # Refine Description for Unclassified
                    final_desc = desc
                    if category == 'OTHER':
                        final_desc = f"[PENDIENTE DE CLASIFICACIÓN] {desc}"

                    CashMovement.objects.create(
                        user=self.user,
                        account=self.account,
                        date=date_val,
                        amount=abs_amount,
                        type=direction,
                        category=category,
                        description=final_desc,
                        external_id=ext_id
                    )
                    stats['created'] += 1
                    
                except Exception as e:
                    stats['errors'] += 1
                    print(f"Row error: {e}")
                    
            return stats
            
        except Exception as e:
            return {'error': f"File Error: {str(e)}"}
