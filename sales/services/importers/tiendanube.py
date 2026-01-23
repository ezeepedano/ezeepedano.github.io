import pandas as pd
import warnings
import gc
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from sales.models import Sale, SaleItem, Product, Customer
from .base import BaseImporter
from sales.services.customer import upsert_customers, build_customer_dedup_key  # We might need to adapt this for Tienda Nube format

class TiendaNubeImporter(BaseImporter):
    def process_file(self, file_obj):
        try:
            warnings.simplefilter("ignore")
            
            # Try encodings and separators
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            separators = [';', ',']
            
            # Read all bytes once
            file_obj.seek(0)
            content_bytes = file_obj.read()
            
            df = None
            errors = []
            
            import io
            
            for encoding in encodings:
                try:
                    # Try to decode to string first
                    content_str = content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    errors.append(f"{encoding}: Decode error")
                    continue
                    
                # Quick sniff for header before full parse
                if 'Número de orden' not in content_str:
                    errors.append(f"{encoding}: Header mismatch (decoded ok)")
                    continue

                for sep in separators:
                    try:
                        # Wrap in StringIO so pandas gets a text stream
                        text_stream = io.StringIO(content_str)
                        
                        # Use engine='python' for robustness
                        df = pd.read_csv(text_stream, sep=sep, engine='python')
                        
                        # Verify columns again to be sure parsing was correct
                        if 'Número de orden' in df.columns:
                            # Strict check for other critical columns to ensure we didn't just get a one-column frame
                            required_cols = ['Nombre del comprador', 'Total', 'Fecha']
                            missing = [c for c in required_cols if c not in df.columns]
                            
                            if not missing:
                                break # Success!
                            else:
                                df = None
                                errors.append(f"{encoding}/{sep}: Key columns missing {missing}. Found: {list(df.columns)}")
                        else:
                            df = None
                            errors.append(f"{encoding}/{sep}: Parsed but 'Número de orden' missing")
                            
                    except Exception as e:
                        errors.append(f"{encoding}/{sep}: {str(e)}")
                        continue
                
                if df is not None:
                    break
            
            if df is None:
                raise ValueError(f"Could not read file. Details: {'; '.join(errors)}")
            
            # Map Tienda Nube columns to expected generic keys if needed, 
            # Or just process directly since column names differ from ML.
            
            # Process in chunks manually if needed, but CSVs are usually lighter than XLS
            # To be safe, we can process row by row from the DF
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        self._process_row(row)
                    except Exception as e:
                        self.stats['errors'] += 1
                        print(f"TN Row error: {e}")

        except Exception as e:
            return {'error': f"Error processing TN file: {str(e)}"}
        
        return self._get_stats_summary()

    def _process_row(self, row):
        order_id = str(row.get('Número de orden'))
        if not order_id or pd.isna(order_id):
            return

        # --- Customer Handling ---
        # We need to adapt upsert_customers logic or do it inline here since format differs from ML
        # ML has 'Comprador' column. TN has 'Nombre del comprador', 'Email', 'DNI / CUIT'
        
        email = row.get('Email', '')
        name = row.get('Nombre del comprador', 'Unknown')
        doc = str(row.get('DNI / CUIT', ''))
        
        # Build a safe dedup key for TN: tiendanube_user_email_doc
        # Prefix with user_id to scope to tenant
        # Use email/doc as uniqueness
        
        # Reuse existing customer logic if possible, or create bespoke minimal customer
        customer = self._get_or_create_customer(row)

        # Validate if this row has main order data (header info)
        # In TN exports, multi-item orders only have header info on the first row.
        # Check if 'Total' or 'Nombre del comprador' is present.
        has_header_data = False
        if not pd.isna(row.get('Total')) and not pd.isna(row.get('Nombre del comprador')):
             has_header_data = True

        # --- Customer Handling ---
        customer = None
        if has_header_data:
            customer = self._get_or_create_customer(row)

        # --- Sale Update/Create ---
        # We first try to get the sale. 
        # If it doesn't exist, we MUST create it, but if this is a sparse row (no header), 
        # we might be creating a skeleton sale waiting for the header row? 
        # Usually header row comes first. But if not, we handle it.
        
        sale, created = Sale.objects.get_or_create(
             order_id=order_id,
             defaults={
                'user': self.user,
                'channel': 'TIENDANUBE', 
                'date': timezone.now(),
                'total': 0,
                'product_revenue': 0,
                'shipping_income': 0,
                'taxes': 0,
                'discounts': 0
             }
        )
        
        if has_header_data:
            # --- Date Parsing ---
            combined_date = row.get('Fecha')
            if pd.isna(combined_date):
                 # Fallback to separate columns if they exist or just now
                 sale_date = timezone.now()
            else:
                 try:
                    dt = datetime.strptime(str(combined_date), "%d/%m/%Y %H:%M:%S")
                    sale_date = timezone.make_aware(dt, timezone.get_current_timezone())
                 except:
                    sale_date = timezone.now()

            # --- Financials ---
            total = self._parse_decimal(row.get('Total'))
            subtotal = self._parse_decimal(row.get('Subtotal de productos'))
            shipping_cost = self._parse_decimal(row.get('Costo de envío'))
            discount = self._parse_decimal(row.get('Descuento'))
            
            shipping_income = shipping_cost
            
            # Update fields
            sale.date = sale_date
            sale.status = row.get('Estado de la orden', 'Abierta')
            sale.customer = customer
            sale.total = total
            sale.product_revenue = subtotal
            sale.shipping_income = shipping_income
            # sale.listing_fee = 0 (default)
            # sale.taxes = 0 (default)
            
            sale.payment_status = self._clean_str(row.get('Estado del pago'))
            sale.shipping_status = self._clean_str(row.get('Estado del envío'))
            sale.currency = self._clean_str(row.get('Moneda', 'ARS'))
            sale.payment_method = self._clean_str(row.get('Medio de pago'))
            sale.transaction_id = self._clean_str(row.get('Identificador de la transacción en el medio de pago')).replace('.0', '')
            sale.payment_date = self._parse_date_safe(row.get('Fecha de pago'))
            
            sale.buyer_notes = self._clean_str(row.get('Notas del comprador'))
            sale.seller_notes = self._clean_str(row.get('Notas del vendedor'))
            
            sale.shipping_date = self._parse_date_safe(row.get('Fecha de envío'))
            sale.recipient_name = self._clean_str(row.get('Nombre para el envío'))
            sale.recipient_phone = self._clean_str(row.get('Teléfono para el envío'))
            sale.shipping_option = self._clean_str(row.get('Medio de envío'))
            sale.tracking_number = self._clean_tracking(row.get('Código de tracking del envío'))
            
            doc = self._clean_str(row.get('DNI / CUIT'))
            sale.buyer_dni = doc
            sale.buyer_address = f"{self._clean_str(row.get('Dirección'))} {self._clean_str(row.get('Número'))} {self._clean_str(row.get('Piso'))} {self._clean_str(row.get('Localidad'))}".strip()
            sale.city = self._clean_str(row.get('Ciudad'))
            sale.province = self._clean_str(row.get('Provincia o estado'))
            sale.zip_code = self._clean_str(row.get('Código postal'))
            sale.invoice_data = f"{self._clean_str(row.get('Nombre del comprador'))} - {doc} ({self._clean_str(row.get('Condición fiscal'))})".strip()
            
            sale.save()
            
            if created:
                self.stats['new_sales'] += 1
            else:
                self.stats['existing_sales'] += 1
        else:
             # Sparse row, likely just an item row attached to existing sale
             pass
            
        # --- Sale Item ---
        sku = self._clean_str(row.get('SKU'))
        
        product_title = self._clean_str(row.get('Nombre del producto') or 'Unknown Item')
        quantity = int(row.get('Cantidad del producto', 1))
        unit_price = self._parse_decimal(row.get('Precio del producto'))
        
        # Check Product Link
        product = None
        if sku:
            product_qs = Product.objects.filter(sku=sku, user=self.user)
            if product_qs.exists():
                product = product_qs.first()
            else:
                self.stats['products_not_found'].add(f"{sku} - {product_title}")

        # Check existing Item
        # TN CSV breaks down items into rows with same order ID.
        # update_or_create of Sale handles header idempotency.
        # Items need to be appended or checked.
        
        item_exists = SaleItem.objects.filter(sale=sale, product_title=product_title, sku=sku).exists()
        
        if not item_exists:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_title=product_title,
                sku=sku,
                quantity=quantity,
                unit_price=unit_price
            )
            
            # Stock update
            if product and status != 'Cancelada':
                 product.stock_quantity -= quantity
                 product.save()

    def _get_or_create_customer(self, row):
        name = self._clean_str(row.get('Nombre del comprador') or 'Unknown')
        doc = self._clean_str(row.get('DNI / CUIT'))
        email = self._clean_str(row.get('Email'))
        
        # Build dedup key
        # We use a custom logic here or adapt the common one
        # Let's simple hash:
        import hashlib
        raw_key = f"TN_{email}_{doc}_{name}".lower().encode('utf-8')
        key_hash = hashlib.sha256(raw_key).hexdigest()
        
        # Scope by User
        scoped_key = f"{self.user.id}_{key_hash}"
        
        customer, created = Customer.objects.get_or_create(
            dedup_key=scoped_key,
            defaults={
                'user': self.user,
                'name': name,
                'email': email,
                'phone': self._parse_phone(row.get('Teléfono')),
                'document_number': doc,
                'billing_name': name,
                'billing_address': f"{self._clean_str(row.get('Dirección'))} {self._clean_str(row.get('Número'))} {self._clean_str(row.get('Piso'))}".strip(),
                'shipping_address': f"{self._clean_str(row.get('Dirección'))} {self._clean_str(row.get('Número'))} {self._clean_str(row.get('Piso'))}".strip(),
                'city': self._clean_str(row.get('Ciudad')),
                'state': self._clean_str(row.get('Provincia o estado')),
                'postal_code': self._clean_str(row.get('Código postal')),
                'country': self._clean_str(row.get('País')),
            }
        )
        # Update existing customer with fresher data (always overwrite to ensure latest info)
        if not created:
             if email: customer.email = email
             phone_val = self._parse_phone(row.get('Teléfono'))
             if phone_val: customer.phone = phone_val
             
             customer.city = self._clean_str(row.get('Ciudad'))
             customer.state = self._clean_str(row.get('Provincia o estado'))
             customer.postal_code = self._clean_str(row.get('Código postal'))
             
             # Also update name/addresses if they were placeholders or now we have better data
             # For now, let's stick to contact info + location which changes most often
             customer.save()
             
        if created:
            self.stats['customers_created'] += 1
        return customer

    def _parse_decimal(self, val):
        if pd.isna(val): return 0
        try:
            val_str = str(val).strip()
            # If comma is present, likely decimal separator in ES locale
            if ',' in val_str:
                # If dot is also present, it's thousands separator (e.g. 1.000,00)
                if '.' in val_str:
                    val_str = val_str.replace('.', '') # Remove thousands
                val_str = val_str.replace(',', '.') # Replace decimal
            return float(val_str)
        except:
            return 0

    def _clean_tracking(self, val):
        if pd.isna(val) or val == 'nan': return ''
        val = str(val)
        # TN exports ="36000..." for excel escaping
        if val.startswith('="') and val.endswith('"'):
            val = val[2:-1]
        return val.strip()

    def _parse_phone(self, val):
        if pd.isna(val) or str(val).strip() == '': return ''
        s = str(val).strip()
        # Handle scientific notation "5,43517E+11" -> "543517..."
        try:
             # Try float first if it looks like float
             f = float(s.replace(',', '.'))
             return str(int(f))
        except:
             return s

    def _parse_date_safe(self, date_val):
        """Parse clean DD/MM/YYYY date or return None."""
        if pd.isna(date_val) or str(date_val).strip() == '':
            return None
        val = str(date_val).strip()
        try:
            # TN CSV dates are usually DD/MM/YYYY without time for payment/shipping dates
            dt = datetime.strptime(val, "%d/%m/%Y")
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except:
            # Try with time if present
            try:
                dt = datetime.strptime(val, "%d/%m/%Y %H:%M:%S")
                return timezone.make_aware(dt, timezone.get_current_timezone())
            except:
                return None

    def _clean_str(self, val):
        """Robust string cleanup for pandas values that might be NaN."""
        if pd.isna(val):
            return ''
        s = str(val).strip()
        if s.lower() == 'nan':
            return ''
        return s
