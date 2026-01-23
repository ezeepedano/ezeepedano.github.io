import pandas as pd
import warnings
import gc
from django.db import transaction
from django.utils import timezone
from sales.models import Sale, SaleItem, Product
from sales.services.cleanup import clean_sales_dataframe
from sales.services.customer import upsert_customers, build_customer_dedup_key
from .base import BaseImporter

class MercadoLibreImporter(BaseImporter):
    def process_file(self, file_obj):
        try:
            warnings.simplefilter("ignore")
            
            # Read full file (pandas read_excel chunksize is flaky across versions)
            df = pd.read_excel(file_obj, header=5)
            
            # Process strictly in memory (if file is huge this might be an issue, but ML excels aren't usually GBs)
            # Or manually chunk the DF
            
            chunk_size = 500
            chunks = [df[i:i+chunk_size] for i in range(0, df.shape[0], chunk_size)]
            
            active_packet_sale = None

            for df_chunk in chunks:
                # 1. Clean Chunk
                df_chunk = clean_sales_dataframe(df_chunk)
                
                # 2. Upsert customers
                try:
                    customer_dedup_map = upsert_customers(df_chunk, self.user)
                    self.stats['customers_created'] += len(customer_dedup_map)
                except Exception as e:
                    print(f"Customer Error in chunk: {e}")
                    customer_dedup_map = {}

                # 3. Process Sales
                with transaction.atomic():
                    for index, row in df_chunk.iterrows():
                        try:
                            self._process_row(row, customer_dedup_map, active_packet_sale)
                        except Exception as e:
                            self.stats['errors'] += 1
                            print(f"Row error: {e}")

                # Memory cleanup
                del df_chunk
                del customer_dedup_map
                gc.collect()

        except Exception as e:
            return {'error': f"Error processing file: {str(e)}"}
        
        return self._get_stats_summary()

    def _process_row(self, row, customer_dedup_map, active_packet_sale):
        row_order_id = str(row.get('# de venta'))
        if not row_order_id or pd.isna(row_order_id) or row_order_id == 'nan':
            return

        buyer_name = row.get('Comprador')
        has_buyer = pd.notna(buyer_name) and str(buyer_name).strip() != ''

        current_sale = None

        if has_buyer:
            dedup_key = build_customer_dedup_key(row)
            customer = customer_dedup_map.get(dedup_key)

            status = str(row.get('Estado del pedido', ''))
            is_packet_header = status.lower().startswith('paquete de')

            # Financials logic from original importer
            prod_income = row.get('Ingresos por productos (ARS)', 0)
            listing_fee = (
                row.get('Cargo por venta', 0) + 
                row.get('Costo fijo', 0) + 
                row.get('Costo por ofrecer cuotas', 0)
            )
            taxes = row.get('Impuestos', 0)
            discounts = row.get('Descuentos', 0)
            
            agg_fee = row.get('Cargo por venta e impuestos (ARS)', 0)
            if listing_fee == 0 and taxes == 0 and agg_fee != 0:
                listing_fee = agg_fee

            shipping_inc = row.get('Ingresos por envío (ARS)', 0)
            shipping_cst = row.get('Costos de envío (ARS)', 0)
            extra_shipping = row.get('Cargo por diferencias en medidas y peso del paquete', 0)
            shipping_cst += extra_shipping
            
            if shipping_inc > 0 and shipping_cst == 0:
                shipping_cst = -shipping_inc

            row_total = (
                prod_income + listing_fee + taxes +
                discounts + shipping_inc + shipping_cst
            )

            sale, created = Sale.objects.update_or_create(
                order_id=row_order_id,
                defaults={
                    'user': self.user,
                    'channel': 'MERCADOLIBRE',
                    'date': row.get('Fecha de venta') if not pd.isna(row.get('Fecha de venta')) else timezone.now(),
                    'status': status,
                    'customer': customer,
                    'total': row_total,
                    'product_revenue': prod_income,
                    'listing_fee': listing_fee,
                    'taxes': taxes,
                    'discounts': discounts,
                    'shipping_income': shipping_inc,
                    'shipping_cost': shipping_cst,
                    'shipping_option': row.get('Forma de entrega', ''),
                    'tracking_number': row.get('Número de seguimiento', ''),
                    'buyer_dni': row.get('DNI', ''),
                    'buyer_address': row.get('Domicilio', ''),
                    'city': row.get('Ciudad', ''),
                    'province': row.get('Estado', ''),
                    'zip_code': row.get('Código postal', ''),
                    'invoice_data': row.get('Datos para su factura', '') or row.get('Datos personales o de empresa', ''),
                }
            )

            if created:
                self.stats['new_sales'] += 1
            else:
                self.stats['existing_sales'] += 1

            current_sale = sale
            
            if is_packet_header:
                active_packet_sale = sale
                return
            else:
                active_packet_sale = None

        else:
            if active_packet_sale:
                current_sale = active_packet_sale
            else:
                return

        # Process Item
        self._process_item(row, current_sale)

    def _process_item(self, row, sale):
        sku = row.get('SKU')
        product_title = row.get('Título de la publicación', 'Unknown')
        quantity = int(row.get('Unidades', 1))
        try:
            unit_price = float(row.get('Precio unitario de venta de la publicación (ARS)', 0))
        except:
            unit_price = 0

        product = None
        if sku and not pd.isna(sku):
            product_qs = Product.objects.filter(sku=sku, user=self.user) 
            if product_qs.exists():
                product = product_qs.first()
            else:
                self.stats['products_not_found'].add(f"{sku} - {product_title}")
        
        item_exists = False
        if sku:
            item_exists = SaleItem.objects.filter(sale=sale, sku=sku).exists()
        else:
            item_exists = SaleItem.objects.filter(sale=sale, product_title=product_title).exists()

        if not item_exists:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_title=product_title,
                sku=sku if sku else '',
                quantity=quantity,
                unit_price=unit_price
            )

            if product and row.get('Estado del pedido') != 'Cancelado':
                product.stock_quantity -= quantity
                product.save()
