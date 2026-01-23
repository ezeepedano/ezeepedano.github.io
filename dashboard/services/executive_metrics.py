from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, F, Avg
from sales.models import Sale, SaleItem
from finance.models import CashMovement, Account
from inventory.models import Product

class ExecutiveMetricsService:
    @staticmethod
    def get_kpis(filters):
        """
        Calculate top-level KPIs based on filters.
        """
        # Date Logic for Comparison
        date_from = filters.get('date__gte')
        date_to = filters.get('date__lte')
        
        # Current Period Data
        sales_current = Sale.objects.filter(**filters)
        
        def calc_aggregates(qs):
            # Debug: Print QS count first
            # count_check = qs.count()
            # print(f"DEBUG: calc_aggregates qs.count() = {count_check}")
            
            agg = qs.aggregate(
                total_revenue=Sum('total'),
                total_product_revenue=Sum('product_revenue'),
            )
            rev = agg['total_revenue'] or Decimal('0.00')
            prod_rev = agg['total_product_revenue'] or Decimal('0.00')
            orders = qs.count()
            
            # Units
            total_units = 0
            if orders > 0:
                 units_agg = SaleItem.objects.filter(sale__in=qs).aggregate(total_units=Sum('quantity'))
                 total_units = units_agg['total_units'] or 0
            
            units = total_units
            
            # Ticket Avg
            ticket = (rev / orders) if orders > 0 else Decimal('0.00')
            
            # COGS (Simplified Estimate)
            cogs = Decimal('0.00')
            if orders > 0:
                 from django.db.models import F
                 items_qs = SaleItem.objects.filter(sale__in=qs).exclude(product=None)
                 cogs_agg = items_qs.aggregate(
                     total_cogs=Sum(F('quantity') * F('product__cost_price'))
                 )
                 cogs = cogs_agg['total_cogs'] or Decimal('0.00')
                
            gross_margin = prod_rev - cogs
            gm_pct = (gross_margin / prod_rev * 100) if prod_rev > 0 else Decimal('0.00')
            
            return {
                'revenue': rev,
                'product_revenue': prod_rev,
                'orders': orders,
                'units': units,
                'ticket_avg': ticket,
                'cogs': cogs,
                'gross_margin': gross_margin,
                'gross_margin_pct': gm_pct,
            }
            
        current_data = calc_aggregates(sales_current)
        
        # Previous Period comparison
        prev_data = None
        growth = {}
        
        if date_from:
            import datetime
            # Parse dates
            if isinstance(date_from, str):
                df = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            else:
                df = date_from
                
            dt = timezone.now().date()
            if date_to:
                 if isinstance(date_to, str):
                    dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                 else:
                    dt = date_to
            
            delta = dt - df
            # Previous range: [start - delta - 1, start - 1]
            # Actually standard is: [start - delta, end - delta] or [start - delta, start]
            # Let's use [start - (end-start), start]
            # Duration = (dt - df).days
            # Prev Start = df - (dt - df) - 1 day?
            # Simple approach: Delta = (dt - df).
            # Prev End = df
            # Prev Start = df - delta
            
            # Fix if delta is 0 (one day) -> 1 day
            days = (dt - df).days + 1
            prev_end = df - timedelta(days=1)
            prev_start = prev_end - timedelta(days=days-1)
            
            prev_filters = filters.copy()
            prev_filters['date__gte'] = prev_start
            prev_filters['date__lte'] = prev_end
            
            # Remove original dates
            # (Using **filters logic, need to override)
            # Since filters uses 'date__gte', updating copies handles it.
            
            sales_prev = Sale.objects.filter(**prev_filters)
            prev_data = calc_aggregates(sales_prev)
            
            # Calculate Growth
            def calc_growth(curr, prev):
                if prev == 0:
                    # If no previous data, return None to indicate no comparison available
                    return None
                if curr == 0 and prev == 0:
                    return 0
                return ((curr - prev) / prev) * 100

            growth['revenue'] = calc_growth(current_data['revenue'], prev_data['revenue'])
            growth['orders'] = calc_growth(current_data['orders'], prev_data['orders'])
            growth['units'] = calc_growth(current_data['units'], prev_data['units'])
            growth['ticket_avg'] = calc_growth(current_data['ticket_avg'], prev_data['ticket_avg'])
            growth['gross_margin'] = calc_growth(current_data['gross_margin'], prev_data['gross_margin'])


        # Merge Results
        result = current_data
        result['growth'] = growth
        result['contribution'] = result['gross_margin'] # Placeholder
        result['contribution_pct'] = result['gross_margin_pct']
        
        return result

    @staticmethod
    def get_sales_trends(filters, bucket='week', window=12):
        """
        Returns sales data aggregated by bucket (week, biweek, month).
        Handles "window" to limit results and fetches previous period for comparison.
        """
        import datetime
        from django.db.models.functions import TruncDate
        
        # 1. Determine Date Range
        date_from_filter = filters.get('date__gte')
        date_to_filter = filters.get('date__lte')
        
        end_date = timezone.now().date()
        if date_to_filter:
            if isinstance(date_to_filter, str):
                end_date = datetime.datetime.strptime(date_to_filter, '%Y-%m-%d').date()
            else:
                end_date = date_to_filter

        # Calculate "Days per bucket" approx for start date calculation
        days_per_bucket = 7
        if bucket == 'biweek' or bucket == '15d': 
            bucket = 'biweek' # Normalize
            days_per_bucket = 15
        elif bucket == 'month': 
            days_per_bucket = 30
        elif bucket == 'day':
            days_per_bucket = 1
        
        # Calculate Start Date
        # Fetch extra to calculate "current" and "previous" stats accurately
        # Window * Bucket * 2 (for previous period) + Buffer
        
        # Performance Safety: If window is huge (e.g., 9999 aka "All"), don't go back centuries.
        # Clamp to the actual first sale date in validity check.
        
        calc_start_date = end_date - timedelta(days=(days_per_bucket * window * 2) + 30)
        
        # Optimization: Fetch earliest sale date
        try:
            earliest_sale = Sale.objects.earliest('date')
            min_db_date = earliest_sale.date.date() if hasattr(earliest_sale.date, 'date') else earliest_sale.date
            
            # If calculated start date is older than DB history, just use DB history (minus buffer for previous period calc if needed)
            if calc_start_date < min_db_date:
                # We still need "previous" period relative to "current".
                # If we want "All", previous is empty.
                # If we use min_db_date, we get all history.
                # Let's ensure start_date is not older than min_db_date - 1 year (margin).
                limit_date = min_db_date - timedelta(days=365)
                if calc_start_date < limit_date:
                    calc_start_date = limit_date
        except Sale.DoesNotExist:
            # No sales, just use recently
            calc_start_date = end_date - timedelta(days=30)

        start_date = calc_start_date
        if date_from_filter:
             # Global filter takes precedence? 
             # For the "Window" functionality to work as expected (Last N), we might want to ignore global date_from 
             # if the context implies a relative window. 
             # However, backend just processes what it gets.
             if isinstance(date_from_filter, str):
                start_date = datetime.datetime.strptime(date_from_filter, '%Y-%m-%d').date()
             else:
                start_date = date_from_filter
        
        # 2. Fetch Daily Data
        query_filters = filters.copy()
        query_filters['date__gte'] = start_date
        query_filters['date__lte'] = end_date
        
        sales_daily = Sale.objects.filter(**query_filters)\
            .annotate(day=TruncDate('date'))\
            .values('day')\
            .annotate(total=Sum('total'))\
            .order_by('day')
            
        daily_map = {entry['day']: entry['total'] for entry in sales_daily}
        
        # 3. Python Re-bucketing
        points = []
        cursor = start_date
        
        # Alignment logic
        if bucket == 'week':
             # Align cursor to Monday (ISO)
             weekday = cursor.weekday() # 0 = Monday
             cursor = cursor - timedelta(days=weekday)
        elif bucket == 'month':
             # Align to 1st of month
             cursor = cursor.replace(day=1)
        # biweek: Anchor to start_date (no shift)
        # day: Anchor to start_date (no shift)
        
        # Generate Buckets
        while cursor <= end_date:
            # Determine End of this bucket
            if bucket == 'week':
                bucket_end = cursor + timedelta(days=6)
            elif bucket == 'biweek':
                bucket_end = cursor + timedelta(days=14)
            elif bucket == 'month':
                # Last day of current month
                next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
                bucket_end = next_month - timedelta(days=1)
            elif bucket == 'day':
                bucket_end = cursor # Start = End for daily
            
            # Sum data in range [cursor, bucket_end]
            val = Decimal(0)
            temp_day = cursor
            while temp_day <= bucket_end:
                val += daily_map.get(temp_day, Decimal(0))
                temp_day += timedelta(days=1)
            
            # Only add if the bucket overlaps with our requested range?
            # Or if it has data? 
            # We add all for continuity.
            points.append({
                'start': cursor.strftime('%Y-%m-%d'),
                'end': bucket_end.strftime('%Y-%m-%d'),
                'value': str(val),
                'numeric_value': val
            })
            
            # Next iteration
            if bucket == 'month':
                 cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            elif bucket == 'week':
                 cursor += timedelta(days=7)
            elif bucket == 'biweek':
                 cursor += timedelta(days=15)
            elif bucket == 'day':
                 cursor += timedelta(days=1)
                 
        # 4. Filter to Window and Calculate Growth
        total_points = len(points)
        is_custom_range = bool(date_from_filter)
        
        if is_custom_range:
             # Just return what fits in range
             final_points = [p for p in points if p['start'] >= str(start_date) and p['end'] <= str(end_date)]
             # Attempt previous comparison if possible?
             # For MVP, calculate comparison on whatever "previous" points exist before the slice
             # But we might not have fetched them if query was strict.
             previous_points = []
        else:
            # Default logic: Slice last N
            if total_points >= window:
                final_points = points[-window:]
                remaining = points[:-window]
                # Previous window
                if len(remaining) >= window:
                    previous_points = remaining[-window:]
                else:
                    previous_points = remaining
            else:
                # Not enough data for full window
                final_points = points
                previous_points = []
                
        # 5. Summary Stats
        current_total = sum(Decimal(p['numeric_value']) for p in final_points) # Use numeric_value for sum
        previous_total = sum(Decimal(p['numeric_value']) for p in previous_points) if previous_points else Decimal(0)
        
        change_pct = 0
        if previous_total > 0:
            change_pct = ((current_total - previous_total) / previous_total) * 100
        elif current_total > 0 and previous_total == 0:
            change_pct = 100 # infinity
            
        return {
            'bucket': bucket,
            'window': window,
            'points': final_points,
            'summary': {
                'current_total': str(current_total),
                'previous_total': str(previous_total),
                'change_pct': round(change_pct, 1)
            }
        }

    @staticmethod
    def get_channel_breakdown(filters):
        """
        Aggregates sales by channel.
        """
        sales = Sale.objects.filter(**filters)
        breakdown = sales.values('channel').annotate(
            revenue=Sum('total'),
            orders=Count('id'),
            # margin?
        ).order_by('-revenue')
        
        # Calculate percentages and margins if possible
        # For now return raw list
        result = list(breakdown)
        
        # If no data, return empty list with a message structure
        if not result:
            return []
        
        return result

    @staticmethod
    def get_top_products(filters, limit=10):
        """
        Top products by revenue within filters.
        """
        # We need to filter SaleItems by the Sale filters (date, channel etc)
        # filters apply to Sale.
        
        items = SaleItem.objects.filter(sale__in=Sale.objects.filter(**filters))
        
        # Aggregate by product
        from django.db.models.functions import Coalesce
        
        # Aggregate by product name (snapshot title if product link missing)
        # keys must not conflict with model fields (sku exists on SaleItem)
        top = items.values(
            display_name=Coalesce('product__name', 'product_title'),
            display_sku=Coalesce('product__sku', 'sku')
        ).annotate(
            revenue=Sum(F('quantity') * F('unit_price')),
            qty=Sum('quantity')
        ).order_by('-revenue')[:limit]
        
        # Remap for frontend consistency
        result = []
        for t in top:
            result.append({
                'product__name': t['display_name'] or 'Unknown Item',
                'product__sku': t['display_sku'],
                'revenue': t['revenue'],
                'qty': t['qty']
            })
        
        return result
        
    @staticmethod
    def get_finance_balances(user):
        """
        Returns live balances for key accounts.
        """
        accounts = Account.objects.filter(user=user, is_active=True)
        balances = []
        
        if not accounts.exists():
            # Return empty list - frontend will show message
            return []
        
        for acc in accounts:
            # Calculate from Movements to be "Live" and robust
            # Filter by user to ensure security
            in_mo = CashMovement.objects.filter(
                user=user,
                account=acc, 
                type='IN'
            ).aggregate(s=Sum('amount'))['s'] or Decimal(0)
            out_mo = CashMovement.objects.filter(
                user=user,
                account=acc, 
                type='OUT'
            ).aggregate(s=Sum('amount'))['s'] or Decimal(0)
            
            # Opening balance usually refers to a start date. 
            # If we want "True" balance: Opening + All IN - All OUT.
            current = acc.opening_balance + in_mo - out_mo
            
            balances.append({
                'id': acc.id,
                'name': acc.name,
                'balance': current,
                'currency': acc.currency,
                'type': acc.get_type_display()
            })
        return balances

    @staticmethod
    def get_recent_movements(user, limit=10):
        return CashMovement.objects.filter(user=user).select_related('account').order_by('-date')[:limit]

    @staticmethod
    def get_aging_preview(user):
        # Receivables (Sales PENDING/PARTIAL)
        # Filter by payment_status and ensure there's a balance to collect
        receivables_qs = Sale.objects.filter(
            user=user, 
            payment_status__in=['PENDING', 'PARTIAL']
        ).filter(
            # Use F() to compare total with paid_amount directly in DB
            # This ensures we only get sales with actual balance
        ).exclude(
            # Exclude where total <= paid_amount (fully paid or overpaid)
        ).order_by('due_date')[:10]
        
        # Filter in Python to use balance property
        receivables = []
        for sale in receivables_qs:
            if sale.balance > 0:  # Only include if there's actual balance
                receivables.append(sale)
        
        # Payables (Purchases)
        payables = []
        try:
            from finance.models import Purchase
            payables_qs = Purchase.objects.filter(
                user=user,
                payment_status__in=['PENDING', 'PARTIAL']
            ).order_by('due_date')[:10]
            
            # Filter in Python to use balance property
            for purchase in payables_qs:
                if purchase.balance > 0:  # Only include if there's actual balance
                    payables.append(purchase)
        except (ImportError, AttributeError):
            # Purchase model doesn't exist or doesn't have these fields
            pass
        
        return {
            'receivables': receivables,
            'payables': payables
        }

    @staticmethod
    def get_stock_alerts(user):
        """
        Velocity based alerts.
        """
        products = Product.objects.filter(user=user).order_by('name')
        alerts = []
        
        # Calculate 30d velocity for all products? Heavy.
        # Optimize: Pre-calculate or do generic.
        # For now, simple loop for Top 50 items?
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        for p in products:
            # Sold in last 30d - filter by user through sale
            sold_qty = SaleItem.objects.filter(
                sale__user=user,
                sale__date__gte=thirty_days_ago, 
                product=p
            ).aggregate(s=Sum('quantity'))['s'] or 0
            
            velocity = sold_qty / 30 if sold_qty > 0 else 0
            
            # Calculate days of coverage
            if p.stock_quantity <= 0:
                days_cover = 0  # Out of stock
            elif velocity > 0:
                days_cover = p.stock_quantity / velocity
            else:
                # No sales in last 30 days, but has stock - show as high coverage
                days_cover = 999
                
            status = 'green'
            if days_cover <= 7:
                status = 'red'
            elif days_cover <= 21:
                status = 'yellow'
                
            if status != 'green': # Only return alerts
                alerts.append({
                    'product': p,
                    'cover': round(days_cover, 1),
                    'status': status,
                    'stock': p.stock_quantity,
                    'velocity_30d': round(sold_qty, 1) # Total sold 30d
                })
        
        # Sort by urgency (red first)
        alerts.sort(key=lambda x: x['cover'])
        return alerts[:20]

    @staticmethod
    def get_customer_metrics(filters):
        """
        RFM segmentation counts.
        """
        # This usually relies on CustomerStats which are pre-calculated.
        # We can just count by segment if existing.
        from sales.models import CustomerStats
        
        segments = CustomerStats.objects.values('segment').annotate(count=Count('id')).order_by('-count')
        return list(segments)
