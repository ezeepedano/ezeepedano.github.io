import logging

import pandas as pd
import gc
from django.db import transaction
from django.utils import timezone
from sales.models import Sale, SaleItem, Product
from sales.services.cleanup import clean_sales_dataframe
from sales.services.customer import upsert_customers, build_customer_dedup_key
from sales.services.stock import StockService
from .base import BaseImporter

logger = logging.getLogger(__name__)

class MercadoLibreImporter(BaseImporter):
    def process_file(self, file_obj):
        try:
            import warnings
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
                    logger.error(f"Customer Error in chunk: {e}")
                    customer_dedup_map = {}

                # 3. Process Sales
                with transaction.atomic():
                    for index, row in df_chunk.iterrows():
                        try:
                            self._process_row(row, customer_dedup_map, active_packet_sale)
                        except Exception as e:
                            self.stats['errors'] += 1
                            logger.error(f"Row error: {e}")

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

            # Financials. MeLi 2026 export ships a definitive ``Total (ARS)``
            # in column 18 — that's the net liquidation amount that ends up
            # in the seller's bank account. We trust it when present and
            # fall back to the historical recompute otherwise (older
            # exports). Also handles the renamed columns:
            #   Estado          → Estado del pedido (status)
            #   Estado.1        → Provincia (province)
            #   Descuentos      → Descuentos y bonificaciones
            prod_income = row.get('Ingresos por productos (ARS)', 0) or 0
            listing_fee = (
                (row.get('Cargo por venta', 0) or 0) +
                (row.get('Costo fijo', 0) or 0) +
                (row.get('Costo por ofrecer cuotas', 0) or 0)
            )
            taxes = row.get('Impuestos', 0) or 0
            # Try both column names so older exports keep working.
            discounts = (
                row.get('Descuentos y bonificaciones', 0)
                or row.get('Descuentos', 0)
                or 0
            )

            agg_fee = row.get('Cargo por venta e impuestos (ARS)', 0) or 0
            if listing_fee == 0 and taxes == 0 and agg_fee != 0:
                listing_fee = agg_fee

            shipping_inc = row.get('Ingresos por envío (ARS)', 0) or 0
            shipping_cst = row.get('Costos de envío (ARS)', 0) or 0
            extra_shipping = row.get('Cargo por diferencias en medidas y peso del paquete', 0) or 0
            shipping_cst += extra_shipping

            if shipping_inc > 0 and shipping_cst == 0:
                shipping_cst = -shipping_inc

            # Authoritative net total from the export, with fallback.
            row_total = row.get('Total (ARS)', None)
            if row_total in (None, '') or pd.isna(row_total):
                row_total = (
                    prod_income + listing_fee + taxes +
                    discounts + shipping_inc + shipping_cst
                )

            # Province lookup — cleanup renamed col36 'Estado' to 'Provincia'.
            province = (
                row.get('Provincia')
                or row.get('Estado.1')
                or ''
            )
            if pd.isna(province):
                province = ''

            sale, created = Sale.objects.update_or_create(
                # Tenant-scoped lookup. Without user= here a re-import by
                # another tenant with the same MeLi order_id would silently
                # overwrite this user's row.
                user=self.user,
                order_id=row_order_id,
                defaults={
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
                    'shipping_option': row.get('Forma de entrega', '') or '',
                    'tracking_number': row.get('Número de seguimiento', '') or '',
                    'buyer_dni': row.get('DNI', '') or '',
                    'buyer_address': row.get('Domicilio', '') or '',
                    'city': row.get('Ciudad', '') or '',
                    'province': province,
                    'zip_code': row.get('Código postal', '') or '',
                    'invoice_data': (
                        row.get('Datos para su factura', '')
                        or row.get('Datos personales o de empresa', '')
                        or ''
                    ),
                    'stock_deducted': status.lower() != 'cancelado',
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
        raw_sku = row.get('SKU')
        product_title = row.get('Título de la publicación', 'Unknown') or 'Unknown'
        try:
            quantity = int(row.get('Unidades', 1) or 1)
        except (ValueError, TypeError):
            quantity = 1
        try:
            unit_price = float(row.get('Precio unitario de venta de la publicación (ARS)', 0) or 0)
        except (ValueError, TypeError):
            unit_price = 0

        # Normalize SKU. Product.sku is stored lowercase (migration 0016)
        # so MeLi's mixed-case SKUs like "creaallinone440nrjPET" must be
        # matched case-insensitively. Empty / NaN → no SKU at all.
        if raw_sku is None or (isinstance(raw_sku, float) and pd.isna(raw_sku)):
            sku_norm = ''
        else:
            sku_norm = str(raw_sku).strip().lower()

        product = None
        if sku_norm:
            product_qs = Product.objects.filter(sku__iexact=sku_norm, user=self.user)
            if product_qs.exists():
                product = product_qs.first()
            else:
                self.stats['products_not_found'].add(f"{sku_norm} - {product_title}")

        # Dedup against existing items on the same sale
        if sku_norm:
            item_exists = SaleItem.objects.filter(sale=sale, sku__iexact=sku_norm).exists()
        else:
            item_exists = SaleItem.objects.filter(sale=sale, product_title=product_title).exists()

        if not item_exists:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_title=product_title,
                sku=sku_norm,
                quantity=quantity,
                unit_price=unit_price
            )

            if product and row.get('Estado del pedido') != 'Cancelado':
                StockService.deduct_item_stock(product, quantity)

