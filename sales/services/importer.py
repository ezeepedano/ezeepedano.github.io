import pandas as pd
import warnings
import gc
from django.db import transaction
from django.utils import timezone
from sales.models import Sale, SaleItem, Product
from .cleanup import clean_sales_dataframe
from .customer import upsert_customers, build_customer_dedup_key

def process_sales_file(file_obj, user):
    """
    Reads an Excel file in chunks, cleans it, imports customers and sales.
    Returns a summary dict.
    """
    stats = {
        'new_sales': 0,
        'existing_sales': 0,
        'errors': 0,
        'products_not_found': set(),
        'customers_created': 0,
        'customers_updated': 0,
    }

    try:
        # Use simplefilter inside the loop or globally here
        warnings.simplefilter("ignore")
        
        # CHUNKED READING:
        # We read in chunks of 500 rows to avoid loading a massive DF into RAM.
        # This helps preventing OOM (SIGKILL) on small instances (Render).
        chunks = pd.read_excel(file_obj, header=5, chunksize=500)
        
        active_packet_sale = None

        for df_chunk in chunks:
            # 1. Clean Chunk
            df_chunk = clean_sales_dataframe(df_chunk)
            
            # 2. Upsert customers for this chunk
            # Note: This might re-process customers seen in previous chunks, 
            # but that is safe (idempotent update).
            try:
                customer_dedup_map = upsert_customers(df_chunk, user)
                stats['customers_created'] += len(customer_dedup_map) # Approximate count (includes verified existing)
            except Exception as e:
                # If customer processing fails for chunk, we might want to skip or log
                print(f"Customer Error in chunk: {e}")
                customer_dedup_map = {}

            # 3. Process Sales in Transaction Batch
            # Grouping 500 inserts into 1 transaction is vastly more efficient 
            # and reduces memory pressure compared to auto-commit per row.
            with transaction.atomic():
                for index, row in df_chunk.iterrows():
                    try:
                        row_order_id = str(row.get('# de venta'))
                        if not row_order_id or pd.isna(row_order_id) or row_order_id == 'nan':
                            continue

                        buyer_name = row.get('Comprador')
                        has_buyer = pd.notna(buyer_name) and str(buyer_name).strip() != ''

                        current_sale = None

                        if has_buyer:
                            # Get customer via dedup_key
                            dedup_key = build_customer_dedup_key(row)
                            customer = customer_dedup_map.get(dedup_key)

                            status = str(row.get('Estado del pedido', ''))
                            is_packet_header = status.lower().startswith('paquete de')

                            # Financials
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
                                prod_income +
                                listing_fee +
                                taxes +
                                discounts +
                                shipping_inc +
                                shipping_cst
                            )

                            sale, created = Sale.objects.update_or_create(
                                order_id=row_order_id,
                                defaults={
                                    'user': user,
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
                                stats['new_sales'] += 1
                            else:
                                stats['existing_sales'] += 1

                            current_sale = sale
                            
                            if is_packet_header:
                                active_packet_sale = sale
                                continue
                            else:
                                active_packet_sale = None

                        else:
                            if active_packet_sale:
                                current_sale = active_packet_sale
                            else:
                                continue

                        # Process Item
                        sku = row.get('SKU')
                        product_title = row.get('Título de la publicación', 'Unknown')
                        quantity = int(row.get('Unidades', 1))
                        try:
                            unit_price = float(row.get('Precio unitario de venta de la publicación (ARS)', 0))
                        except:
                            unit_price = 0

                        product = None
                        if sku and not pd.isna(sku):
                            product_qs = Product.objects.filter(sku=sku, user=user) 
                            if product_qs.exists():
                                product = product_qs.first()
                            else:
                                stats['products_not_found'].add(f"{sku} - {product_title}")
                        
                        item_exists = False
                        if sku:
                            item_exists = SaleItem.objects.filter(sale=current_sale, sku=sku).exists()
                        else:
                            item_exists = SaleItem.objects.filter(sale=current_sale, product_title=product_title).exists()

                        if not item_exists:
                            SaleItem.objects.create(
                                sale=current_sale,
                                product=product,
                                product_title=product_title,
                                sku=sku if sku else '',
                                quantity=quantity,
                                unit_price=unit_price
                            )

                            if product and row.get('Estado del pedido') != 'Cancelado':
                                product.stock_quantity -= quantity
                                product.save()

                    except Exception as e:
                        # Log error but continue chunk
                        stats['errors'] += 1
                        print(f"Row error: {e}")

            # End of Chunk Transaction
            # Manual Garbage Collection to free memory
            del df_chunk
            del customer_dedup_map
            gc.collect()

    except Exception as e:
        return {'error': f"Error process file: {str(e)}"}
    
    stats['products_not_found'] = list(stats['products_not_found'])
    return stats
