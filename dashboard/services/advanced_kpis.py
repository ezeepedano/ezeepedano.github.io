"""
Cálculo de KPIs Avanzados para Business Intelligence
"""
from django.db.models import Sum, Avg, F, Q, Count, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import datetime, timedelta
from sales.models import Sale, Customer
from inventory.models import Product
from finance.models import Purchase, CashMovement


class AdvancedKPICalculator:
    """Calculadora de KPIs avanzados para BI"""
    
    @staticmethod
    def calculate_gmroi(user, product_id=None, date_from=None, date_to=None):
        """
        GMROI (Gross Margin Return on Investment)
        Fórmula: Margen Bruto / Costo Promedio de Inventario
        
        Interpretación:
        - GMROI > 1: El producto genera más margen que el costo de mantenerlo
        - GMROI < 1: El producto no es rentable considerando el inventario
        """
        from sales.models import SaleItem
        
        # Filtro base
        filters = {'product__user': user}
        if product_id:
            filters['product_id'] = product_id
        if date_from and date_to:
            filters['sale__date__range'] = [date_from, date_to]
        
        # Calcular por producto
        results = SaleItem.objects.filter(**filters).values(
            'product__id', 
            'product__name',
            'product__sku',
            'product__cost_price',
            'product__stock_quantity'
        ).annotate(
            # Ingresos totales
            total_revenue=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price'),
                    output_field=DecimalField()
                )
            ),
            # Costo de ventas
            cogs=Sum(
                ExpressionWrapper(
                    F('quantity') * F('product__cost_price'),
                    output_field=DecimalField()
                )
            ),
            # Cantidad vendida
            units_sold=Sum('quantity')
        )
        
        gmroi_data = []
        for item in results:
            revenue = item['total_revenue'] or Decimal('0')
            cogs = item['cogs'] or Decimal('0')
            gross_margin = revenue - cogs
            
            # Valor promedio de inventario (simplificado: stock actual * costo)
            stock = item['product__stock_quantity'] or 0
            cost_price = item['product__cost_price'] or Decimal('0')
            avg_inventory_value = Decimal(stock) * cost_price
            
            # Calcular GMROI
            gmroi = (gross_margin / avg_inventory_value) if avg_inventory_value > 0 else Decimal('0')
            
            # Calcular rotación de inventario
            turnover = (item['units_sold'] / Decimal(stock)) if stock > 0 else Decimal('0')
            
            # Clasificación
            if gmroi > Decimal('3') and turnover > Decimal('2'):
                classification = "ESTRELLA"  # Alta rentabilidad, alta rotación
            elif gmroi > Decimal('3'):
                classification = "VACA LECHERA"  # Alta rentabilidad, baja rotación
            elif turnover > Decimal('2'):
                classification = "INTERROGANTE"  # Baja rentabilidad, alta rotación
            else:
                classification = "PERRO"  # Baja rentabilidad, baja rotación
            
            gmroi_data.append({
                'product_id': item['product__id'],
                'product_name': item['product__name'],
                'sku': item['product__sku'],
                'revenue': float(revenue),
                'cogs': float(cogs),
                'gross_margin': float(gross_margin),
                'margin_percent': float((gross_margin / revenue * 100) if revenue > 0 else 0),
                'avg_inventory_value': float(avg_inventory_value),
                'gmroi': float(gmroi),
                'turnover': float(turnover),
                'classification': classification,
                'units_sold': item['units_sold']
            })
        
        # Ordenar por GMROI descendente
        gmroi_data.sort(key=lambda x: x['gmroi'], reverse=True)
        
        return gmroi_data
    
    @staticmethod
    def calculate_cash_conversion_cycle(user, date_from, date_to):
        """
        CCC (Cash Conversion Cycle) - Ciclo de Conversión de Efectivo
        Fórmula: DIO + DSO - DPO
        
        DIO (Days Inventory Outstanding): Días que tarda en venderse el inventario
        DSO (Days Sales Outstanding): Días que tarda en cobrarse una venta
        DPO (Days Payable Outstanding): Días que tardamos en pagar a proveedores
        
        Interpretación:
        - CCC < 0: Cobramos antes de pagar (¡excelente!)
        - CCC 0-30: Muy bueno
        - CCC 30-60: Aceptable
        - CCC > 60: Mejorable
        """
        days_in_period = (date_to - date_from).days or 1
        
        # 1. DIO - Days Inventory Outstanding
        # Inventario promedio / (COGS / días)
        products = Product.objects.filter(user=user)
        avg_inventory_value = products.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('stock_quantity') * F('cost_price'),
                    output_field=DecimalField()
                )
            )
        )['total'] or Decimal('0')
        
        # COGS del período
        from sales.models import SaleItem
        cogs = SaleItem.objects.filter(
            sale__user=user,
            sale__date__range=[date_from, date_to]
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') * F('product__cost_price'),
                    output_field=DecimalField()
                )
            )
        )['total'] or Decimal('0')
        
        dio = (avg_inventory_value / (cogs / days_in_period)) if cogs > 0 else Decimal('0')
        
        # 2. DSO - Days Sales Outstanding
        # Cuentas por cobrar promedio / (Ventas / días)
        avg_receivables = Sale.objects.filter(
            user=user,
            payment_status__in=['PENDING', 'PARTIAL']
        ).aggregate(
            total=Sum('total') - Sum('paid_amount')
        )
        avg_receivables = (avg_receivables['total'] or Decimal('0')) - (avg_receivables['total'] or Decimal('0'))
        
        total_sales = Sale.objects.filter(
            user=user,
            date__range=[date_from, date_to]
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        dso = (avg_receivables / (total_sales / days_in_period)) if total_sales > 0 else Decimal('0')
        
        # 3. DPO - Days Payable Outstanding
        # Cuentas por pagar promedio / (Compras / días)
        avg_payables = Purchase.objects.filter(
            user=user,
            payment_status__in=['PENDING', 'PARTIAL']
        ).aggregate(
            total=Sum('amount') - Sum('paid_amount')
        )
        avg_payables = (avg_payables['total'] or Decimal('0')) - (avg_payables['total'] or Decimal('0'))
        
        total_purchases = Purchase.objects.filter(
            user=user,
            date__range=[date_from, date_to]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        dpo = (avg_payables / (total_purchases / days_in_period)) if total_purchases > 0 else Decimal('0')
        
        # CCC = DIO + DSO - DPO
        ccc = dio + dso - dpo
        
        # Interpretación
        if ccc < 0:
            interpretation = "EXCELENTE"
            recommendation = "Está cobrando antes de pagar. ¡Mantenga esta posición!"
        elif ccc < 30:
            interpretation = "MUY BUENO"
            recommendation = "Buena gestión de capital de trabajo."
        elif ccc < 60:
            interpretation = "ACEPTABLE"
            recommendation = "Considere acelerar cobranzas o negociar mayores plazos con proveedores."
        else:
            interpretation = "MEJORABLE"
            recommendation = "CRÍTICO: Riesgo de problemas de liquidez. Priorice cobranzas y optimice inventario."
        
        return {
            'dio': float(dio),
            'dso': float(dso),
            'dpo': float(dpo),
            'ccc': float(ccc),
            'interpretation': interpretation,
            'recommendation': recommendation,
            'metrics': {
                'avg_inventory_value': float(avg_inventory_value),
                'cogs': float(cogs),
                'avg_receivables': float(avg_receivables),
                'total_sales': float(total_sales),
                'avg_payables': float(avg_payables),
                'total_purchases': float(total_purchases)
            }
        }
    
    @staticmethod
    def calculate_customer_lifetime_value(user, customer_id=None):
        """
        CLV (Customer Lifetime Value) - Valor de Vida del Cliente
        
        Versión simplificada:
        CLV = (Ticket Promedio × Frecuencia de Compra × Vida del Cliente) - Costo de Adquisición
        """
        filters = {'user': user}
        if customer_id:
            filters['id'] = customer_id
        
        customers = Customer.objects.filter(**filters)
        
        clv_data = []
        for customer in customers:
            stats = customer.safe_stats
            if not stats:
                continue
            
            # Calcular frecuencia anual proyectada
            if stats.first_order_date and stats.last_order_date:
                days_active = (stats.last_order_date - stats.first_order_date).days or 1
                purchases_per_year = (stats.total_orders / days_active) * 365 if days_active > 0 else 0
            else:
                purchases_per_year = 0
            
            # Vida del cliente proyectada (en años) - asumimos 3 años promedio
            customer_lifespan = 3
            
            # CLV simplificado (sin costo de adquisición por ahora)
            avg_ticket = stats.avg_ticket or Decimal('0')
            clv = avg_ticket * Decimal(str(purchases_per_year)) * Decimal(str(customer_lifespan))
            
            # Probabilidad de retención (basada en recencia)
            if stats.days_since_last_order < 30:
                retention_probability = 0.9
            elif stats.days_since_last_order < 90:
                retention_probability = 0.7
            elif stats.days_since_last_order < 180:
                retention_probability = 0.4
            else:
                retention_probability = 0.1
            
            clv_adjusted = clv * Decimal(str(retention_probability))
            
            clv_data.append({
                'customer_id': customer.id,
                'customer_name': customer.name,
                'total_spent': float(stats.total_spent),
                'avg_ticket': float(avg_ticket),
                'total_orders': stats.total_orders,
                'purchases_per_year': round(purchases_per_year, 2),
                'clv_raw': float(clv),
                'retention_probability': retention_probability,
                'clv_adjusted': float(clv_adjusted),
                'days_since_last_order': stats.days_since_last_order,
                'segment': stats.segment
            })
        
        # Ordenar por CLV ajustado
        clv_data.sort(key=lambda x: x['clv_adjusted'], reverse=True)
        
        return clv_data
    
    @staticmethod
    def calculate_abc_analysis(user):
        """
        Análisis ABC de Productos (Principio de Pareto)
        
        A: 20% de productos que generan 80% de ingresos
        B: 30% de productos que generan 15% de ingresos
        C: 50% de productos que generan 5% de ingresos
        """
        from sales.models import SaleItem
        
        # Ventas por producto
        product_sales = SaleItem.objects.filter(
            sale__user=user
        ).values(
            'product__id',
            'product__name',
            'product__sku'
        ).annotate(
            total_revenue=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price'),
                    output_field=DecimalField()
                )
            ),
            total_quantity=Sum('quantity')
        ).order_by('-total_revenue')
        
        # Calcular total general
        total_revenue = sum([p['total_revenue'] or 0 for p in product_sales])
        
        # Clasificar en ABC
        cumulative_revenue = 0
        abc_products = []
        
        for product in product_sales:
            revenue = product['total_revenue'] or 0
            cumulative_revenue += revenue
            cumulative_percent = (cumulative_revenue / total_revenue * 100) if total_revenue > 0 else 0
            
            if cumulative_percent <= 80:
                category = 'A'
            elif cumulative_percent <= 95:
                category = 'B'
            else:
                category = 'C'
            
            abc_products.append({
                'product_id': product['product__id'],
                'product_name': product['product__name'],
                'sku': product['product__sku'],
                'revenue': float(revenue),
                'quantity_sold': product['total_quantity'],
                'revenue_percent': float((revenue / total_revenue * 100) if total_revenue > 0 else 0),
                'cumulative_percent': float(cumulative_percent),
                'category': category
            })
        
        return {
            'products': abc_products,
            'summary': {
                'total_revenue': float(total_revenue),
                'category_a_count': len([p for p in abc_products if p['category'] == 'A']),
                'category_b_count': len([p for p in abc_products if p['category'] == 'B']),
                'category_c_count': len([p for p in abc_products if p['category'] == 'C']),
            }
        }
