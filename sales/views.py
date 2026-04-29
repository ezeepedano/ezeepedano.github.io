import uuid
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction


def _recalculate_sale_totals(sale):
    """
    Recompute ``Sale.product_revenue`` and ``Sale.total`` from the items
    currently persisted in the database.

    The naive pattern ``for item in formset.save(commit=False): total +=
    item.quantity * item.unit_price`` only walks the **new and modified**
    forms — unchanged existing rows are silently skipped. When a user edits
    a 19-line sale and only touches one row, that pattern overwrites the
    sale total with that one row's subtotal. This helper sidesteps the
    issue by aggregating the live DB state.

    Returns the recomputed ``total`` (a Decimal) for convenience.
    """
    agg = sale.items.all().aggregate(
        subtotal=Sum(
            ExpressionWrapper(
                F('quantity') * F('unit_price'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
    )
    subtotal = agg['subtotal'] or Decimal('0')
    shipping = sale.shipping_cost or Decimal('0')
    discounts = sale.discounts or Decimal('0')

    sale.product_revenue = subtotal
    sale.total = subtotal + shipping - discounts
    sale.save(update_fields=['product_revenue', 'total'])
    return sale.total

from .forms import UploadFileForm, SaleForm, SaleItemFormSet, CustomerForm
from .services.importer import process_sales_file
from .models import Sale, Customer, CustomerStats, Product, SaleItem
from finance.services import FinanceService
from finance.models import CashMovement
from sales.services.stock import StockService
from core_erp.pdf_utils import render_to_pdf
from production.models import CompanyConfig
import os
from django.conf import settings
@login_required
def sale_create(request):
    """Create a new manual sale (generic)."""
    if request.method == 'POST':
        form = SaleForm(request.POST, user=request.user)
        formset = SaleItemFormSet(request.POST, form_kwargs={'user': request.user})
        
        if form.is_valid() and formset.is_valid():
            sale = form.save(commit=False)
            sale.user = request.user
            
            # Capture financial input
            param_paid_amount = sale.paid_amount or 0
            param_account = form.cleaned_data.get('payment_account')
            
            # Sync Address from Customer
            if sale.customer:
                sale.buyer_address = sale.customer.billing_address
                sale.city = sale.customer.city
                sale.province = sale.customer.state
                sale.recipient_name = sale.customer.name # Default recipient
                sale.buyer_dni = sale.customer.document_number
            
            # Reset paid_amount initially to ensure clean state
            sale.paid_amount = 0
            
            # Generate a unique order ID for manual sales if not provided
            # Format: MAN-{YYYYMMDD}-{Random/Sequence}
            # Generate a unique order ID for manual sales if not provided
            # Format: MAN-{YYYYMMDD}-{Sequence}
            if not sale.order_id:
                today_str = timezone.now().strftime('%Y%m%d')
                prefix = f"MAN-{today_str}-"
                last_sale = Sale.objects.filter(user=request.user, order_id__startswith=prefix).order_by('order_id').last()
                
                if last_sale:
                    try:
                        last_seq = int(last_sale.order_id.split('-')[-1])
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                    
                sale.order_id = f"{prefix}{new_seq:02d}"
            
            # Helper to calc total
            sale.total = 0 # Will update after items
            sale.status = 'COMPLETED' # Default for manual entry
            sale.save()
            
            # Save items
            items = formset.save(commit=False)
            for item in items:
                item.sale = sale
                item.product_title = item.product.name if item.product else "Unknown Product"
                item.sku = item.product.sku if item.product else ""
                item.save()

            # Update totals — aggregated from the DB rather than from the
            # formset's iterator, which only includes new/changed forms.
            _recalculate_sale_totals(sale)

            # DEDUCT STOCK
            StockService.deduct_sale_stock(sale)
            
            sale.save()
            
            # PROCESS PAYMENT (Integration with Finance)
            if param_paid_amount > 0:
                if param_account:
                    # Automatic CashMovement + Status Update
                    FinanceService.register_payment(
                        target_object=sale,
                        account=param_account,
                        amount=param_paid_amount,
                        date=sale.date,
                        description=f"Cobro Venta #{sale.order_id}"
                    )
                else:
                    # Manual Update (No Cash Impact)
                    sale.paid_amount = param_paid_amount
                    if sale.paid_amount >= sale.total:
                        sale.payment_status = 'PAID'
                    else:
                        sale.payment_status = 'PARTIAL'
                    sale.save()
            else:
                 # Ensure consistency if 0 paid
                 sale.payment_status = 'PENDING'
                 sale.save()
            
            # Initial stats update (simple)
            # ideally we'd use a service or signal, but let's do basic increment
            if sale.customer and hasattr(sale.customer, 'stats'):
                 stats = sale.customer.stats
                 stats.total_orders += 1
                 stats.total_spent += sale.total
                 stats.last_order_date = sale.date
                 stats.save()

            messages.success(request, f'Venta mayorista #{sale.order_id} registrada.')
            return redirect('sales_dashboard')
    else:
        initial_data = {'date': timezone.now()}
        if request.GET.get('customer'):
            initial_data['customer'] = request.GET.get('customer')
            
        form = SaleForm(initial=initial_data, user=request.user)
        formset = SaleItemFormSet(form_kwargs={'user': request.user})
        
    return render(request, 'sales/wholesale_form.html', {'form': form, 'formset': formset, 'title': 'Agregar Venta'})

@login_required
def tiendanube_create(request):
    """Create a new manual Tienda Nube sale."""
    if request.method == 'POST':
        form = SaleForm(request.POST, user=request.user)
        formset = SaleItemFormSet(request.POST, form_kwargs={'user': request.user})
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.user = request.user
                
                # Generate Order ID
                sale.order_id = f"TN-{int(timezone.now().timestamp())}"
                sale.save()
                
                formset.instance = sale
                formset.save()
                
                # Update stock
                sync_sale_stock(sale, reverse=False)
                sale.stock_deducted = True
                sale.save()
                        
            messages.success(request, 'Venta de Tienda Nube creada exitosamente.')
            return redirect('sales_dashboard')
    else:
        initial_data = {'date': timezone.now(), 'channel': 'TIENDANUBE'}
        form = SaleForm(initial=initial_data, user=request.user)
        formset = SaleItemFormSet(form_kwargs={'user': request.user})
        
    return render(request, 'sales/wholesale_form.html', {'form': form, 'formset': formset, 'title': 'Nueva Venta Tienda Nube'})


@login_required
def sales_dashboard(request):
    """Main sales listing page with search, date filters, and pagination."""
    from django.core.paginator import Paginator
    from django.db.models import Q

    channel = request.GET.get('channel')
    search = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    sales_qs = Sale.objects.filter(
        user=request.user
    ).select_related('customer').prefetch_related('items')

    # Sorting
    sort_field = request.GET.get('sort', 'date')
    sort_order = request.GET.get('order', 'desc')
    allowed_sorts = {'date': 'date', 'total': 'total', 'status': 'status'}
    sort_col = allowed_sorts.get(sort_field, 'date')
    order_prefix = '-' if sort_order == 'desc' else ''
    sales_qs = sales_qs.order_by(f'{order_prefix}{sort_col}')

    if channel:
        sales_qs = sales_qs.filter(channel=channel)

    if search:
        sales_qs = sales_qs.filter(
            Q(customer__name__icontains=search) |
            Q(order_id__icontains=search) |
            Q(items__product_title__icontains=search)
        ).distinct()

    if date_from:
        sales_qs = sales_qs.filter(date__date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(date__date__lte=date_to)

    last_updated = sales_qs.first()
    last_updated = last_updated.updated_at if last_updated else None

    paginator = Paginator(sales_qs, 50)
    page_number = request.GET.get('page')
    sales = paginator.get_page(page_number)

    return render(request, 'sales/dashboard.html', {
        'sales': sales,
        'last_updated': last_updated,
        'current_channel': channel,
        'search_query': search,
        'date_from': date_from,
        'date_to': date_to,
        'sort_field': sort_field,
        'sort_order': sort_order,
    })


@login_required
def sale_detail(request, pk):
    """Individual sale detail page."""
    sale = get_object_or_404(Sale.objects.filter(user=request.user).select_related('customer'), pk=pk)
    return render(request, 'sales/detail.html', {'sale': sale})


@login_required
def sale_pdf(request, pk):
    """Generate PDF (Remito) for a sale."""
    sale = get_object_or_404(
        Sale.objects.filter(user=request.user).select_related('customer').prefetch_related('items__product'),
        pk=pk
    )
    config = CompanyConfig.get_config()

    # Logo
    logo_path = None
    if config.logo_image and hasattr(config.logo_image, 'path') and os.path.exists(config.logo_image.path):
        logo_path = config.logo_image.path
    else:
        static_logo = os.path.join(settings.BASE_DIR, 'static', 'img', 'logos', 'logo_main.png')
        if not os.path.exists(static_logo):
            static_logo = os.path.join(settings.BASE_DIR, 'static', 'img', 'logos', 'logo_report.png')
        if os.path.exists(static_logo):
            logo_path = static_logo

    # Items data
    items = sale.items.all()
    total_qty = sum(item.quantity for item in items)

    filename = f"Remito_{sale.order_id}.pdf"
    ctx = {
        'sale': sale,
        'items': items,
        'total_items': total_qty,
        'config': config,
        'company_name': config.company_name,
        'logo_path': logo_path,
        'print_user': request.user.get_full_name() or request.user.username,
    }

    return render_to_pdf('reports/sale_pdf.html', ctx, filename)


@login_required
def upload_sales(request):
    """Handle Excel file upload for sales import."""
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Pass user to processing service
            result = process_sales_file(request.FILES['file'], request.user)
            
            if 'error' in result:
                messages.error(request, result['error'])
            else:
                # Top-level success summary
                bits = [
                    f"{result.get('new_sales', 0)} ventas nuevas",
                    f"{result.get('existing_sales', 0)} actualizadas",
                ]
                if result.get('customers_created'):
                    bits.append(f"{result['customers_created']} clientes nuevos")
                if result.get('errors'):
                    bits.append(f"{result['errors']} errores")
                messages.success(request, "Importación OK: " + " · ".join(bits))

                # Per-issue warning so the user knows which SKUs to load
                missing = result.get('products_not_found') or []
                if missing:
                    preview = ", ".join(sorted(set(missing))[:5])
                    suffix = "" if len(missing) <= 5 else f" (+{len(missing)-5} más)"
                    messages.warning(
                        request,
                        f"{len(missing)} SKUs del Excel no existen en tu inventario y "
                        f"quedaron sin link a producto: {preview}{suffix}. "
                        f"Cargalos en /inventory/ para que las próximas importaciones "
                        f"los liguen automáticamente."
                    )

            return redirect('sales_dashboard')
    else:
        form = UploadFileForm()
    return render(request, 'sales/upload.html', {'form': form})


@login_required
def sale_edit(request, pk):
    """Edit an existing sale."""
    sale = get_object_or_404(Sale.objects.filter(user=request.user), pk=pk)
    
    if request.method == 'POST':
        form = SaleForm(request.POST, instance=sale, user=request.user)
        formset = SaleItemFormSet(request.POST, instance=sale, form_kwargs={'user': request.user})
        
        if form.is_valid() and formset.is_valid():
            
            # 1. Restore Stock (if previously deducted)
            # Must be done BEFORE saving new state implies destroying old state?
            # Actually, we can do it on the existing DB state.
            if sale.stock_deducted:
                 StockService.restore_sale_stock(sale)

            sale = form.save(commit=False)
            
            # Sync Address from Customer (Update on Edit too)
            if sale.customer:
                sale.buyer_address = sale.customer.billing_address
                sale.city = sale.customer.city
                sale.province = sale.customer.state
                sale.recipient_name = sale.customer.name
                sale.buyer_dni = sale.customer.document_number
            
            # Recalculate Logic same as create
            sale.save()
            
            items = formset.save(commit=False)

            # Handle deleted items first
            for obj in formset.deleted_objects:
                obj.delete()

            # Save new + modified items. Note: ``items`` deliberately does
            # NOT include rows the user left untouched — we don't need to
            # re-save them, only count them in the total below.
            for item in items:
                item.sale = sale
                item.product_title = item.product.name if item.product else "Unknown Product"
                item.sku = item.product.sku if item.product else ""
                item.save()

            # DEDUCT STOCK (New State)
            StockService.deduct_sale_stock(sale)

            # Recalculate totals from the live DB state — this fixes the
            # historic bug where editing a multi-line sale overwrote the
            # total with just the touched line's subtotal (e.g. sale
            # MAN-20260421-01 ended up at $24,700 instead of $524,077).
            _recalculate_sale_totals(sale)
            
            # Financial Update Logic
            param_account = form.cleaned_data.get('payment_account')
            param_paid_amount = sale.paid_amount or 0
            
            # ContentType and CashMovement imported at module level
            
            ct = ContentType.objects.get_for_model(Sale)
            existing_movement = CashMovement.objects.filter(content_type=ct, object_id=sale.pk).first()
            
            if param_paid_amount > 0 and param_account:
                if existing_movement:
                    # Update existing
                    existing_movement.account = param_account
                    existing_movement.amount = param_paid_amount
                    existing_movement.date = sale.date
                    existing_movement.description = f"Cobro Venta #{sale.order_id}"
                    existing_movement.save()
                else:
                    # Create new
                    FinanceService.register_payment(
                        target_object=sale,
                        account=param_account,
                        amount=param_paid_amount,
                        date=sale.date,
                        description=f"Cobro Venta #{sale.order_id}"
                    )
            elif existing_movement:
                # If amount is 0 or no account selected, but movement exists -> Delete it
                existing_movement.delete()

            # Update Payment status logic (Simple recalc)
            if sale.paid_amount >= sale.total:
                sale.payment_status = 'PAID'
            elif sale.paid_amount > 0:
                sale.payment_status = 'PARTIAL'
            else:
                sale.payment_status = 'PENDING'
                
            sale.save()
            
            messages.success(request, f'Venta #{sale.order_id} actualizada.')
            return redirect('sale_detail', pk=sale.pk)
    else:
        form = SaleForm(instance=sale, user=request.user)
        formset = SaleItemFormSet(instance=sale, form_kwargs={'user': request.user})
        
    return render(request, 'sales/wholesale_form.html', {
        'form': form, 
        'formset': formset, 
        'title': f'Editar Venta #{sale.order_id}'
    })

# =============================================================================
# CUSTOMER VIEWS
# =============================================================================

@login_required
def customer_list(request):
    """
    Customer listing with filtering and sorting.
    """
    
    customers = Customer.objects.filter(user=request.user).prefetch_related('stats').all()
    
    # Filters
    segment = request.GET.get('segment')
    if segment:
        customers = customers.filter(stats__segment=segment)
    
    has_claims = request.GET.get('claims')
    if has_claims == '1':
        customers = customers.filter(has_open_claim=True)
    
    state = request.GET.get('state')
    if state:
        customers = customers.filter(state__icontains=state)
    
    search = request.GET.get('q')
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(billing_name__icontains=search) |
            Q(document_number__icontains=search)
        )
    
    # Sorting
    sort = request.GET.get('sort', '-stats__total_spent')
    valid_sorts = [
        'stats__total_spent', '-stats__total_spent',
        'stats__total_orders', '-stats__total_orders',
        'stats__days_since_last_order', '-stats__days_since_last_order',
        'name', '-name',
        '-last_purchase_date', 'last_purchase_date',
    ]
    if sort in valid_sorts:
        customers = customers.order_by(sort)
    else:
        customers = customers.order_by('-stats__total_spent')
    
    # Get segment options for filter dropdown
    # Note: CustomerStats doesn't have a user field directly in original update?
    # I didn't add it in the prompt, I only added it to Customer.
    # So I must query via Customer or relying on the initial `customers` queryset which is user filtered.
    # But here I am querying `CustomerStats` directly for distinct segments.
    # This queries ALL stats. I need to filter.
    # segments = CustomerStats.objects.filter(customer__user=request.user)...
    segments = CustomerStats.objects.filter(customer__user=request.user).values_list('segment', flat=True).distinct()
    
    context = {
        'customers': customers,
        'segments': [s for s in segments if s],
        'current_segment': segment,
        'current_sort': sort,
        'search_query': search or '',
    }
    
    return render(request, 'sales/customers/list.html', context)


@login_required
def customer_create(request):
    """
    Create a new customer manually.
    """
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.user = request.user
            
            # Generate unique dedup_key for manual entry
            import uuid
            customer.dedup_key = f"manual_{request.user.id}_{uuid.uuid4().hex}"
            
            customer.save()
            
            messages.success(request, f'Cliente {customer.name} creado exitosamente.')
            
            if 'save_and_sale' in request.POST:
                return redirect(f"{reverse('sale_create')}?customer={customer.id}")
            return redirect('customer_list')
    else:
        initial = {}
        if request.GET.get('name'):
            initial['name'] = request.GET.get('name')
        form = CustomerForm(initial=initial)
    
    return render(request, 'sales/customers/form.html', {'form': form})


@login_required
def customer_detail(request, pk):
    """
    Customer detail/dashboard page.
    """
    from django.core.paginator import Paginator
    from django.db.models.functions import TruncMonth
    from django.db.models import Sum, Count

    customer = get_object_or_404(
        Customer.objects.filter(user=request.user).select_related('stats'),
        pk=pk
    )

    # Defense in depth: customer is already user-scoped above, but pin the
    # related queries to user= as well so any future refactor doesn't leak.
    sales_qs = Sale.objects.filter(customer=customer, user=request.user).order_by('-date')
    paginator = Paginator(sales_qs, 20)
    page_number = request.GET.get('page')
    sales = paginator.get_page(page_number)

    # Top products (qty) + revenue, dedup by product (when linked) or by title.
    top_products = (
        SaleItem.objects
        .filter(sale__customer=customer, sale__user=request.user)
        .values('product_title', 'sku')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'), output_field=DecimalField()),
        )
        .order_by('-total_qty')[:8]
    )

    # Monthly purchases for chart (last 12 months)
    import django.db.models as django_models
    monthly_purchases = list(
        Sale.objects.filter(customer=customer, user=request.user)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            revenue=django_models.Sum('total'),
            orders=django_models.Count('id')
        )
        .order_by('month')
    )
    # Convert to JSON-safe format
    import json
    monthly_chart_data = json.dumps([
        {
            'month': item['month'].strftime('%Y-%m') if item['month'] else '',
            'revenue': float(item['revenue'] or 0),
            'orders': item['orders'],
        }
        for item in monthly_purchases
    ][-12:])

    # Get customer's quotations
    from .models import Quotation
    quotations = Quotation.objects.filter(
        customer=customer, user=request.user
    ).order_by('-date')[:10]

    context = {
        'customer': customer,
        'stats': getattr(customer, 'stats', None),
        'sales': sales,
        'top_products': top_products,
        'monthly_chart_data': monthly_chart_data,
        'quotations': quotations,
    }

    return render(request, 'sales/customers/detail.html', context)

@login_required
def customer_detail_api(request, pk):
    """API to get customer details for frontend (Map)."""
    customer = get_object_or_404(Customer, pk=pk, user=request.user)
    data = {
        'billing_address': customer.billing_address,
        'city': customer.city,
        'state': customer.state,
        'name': customer.name
    }
    return JsonResponse(data)

@login_required
def product_detail_api(request, pk):
    """API to get product details (price) for frontend."""
    product = get_object_or_404(Product, pk=pk, user=request.user)
    data = {
        'price': product.sale_price,
        'sku': product.sku,
        'name': product.name
    }
    return JsonResponse(data)

@login_required
def customer_edit(request, pk):
    """Edit customer details."""
    customer = get_object_or_404(Customer, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cliente {customer.name} actualizado.')
            return redirect('customer_detail', pk=pk)
    else:
        form = CustomerForm(instance=customer)
        
    return render(request, 'sales/customers/form.html', {'form': form, 'title': f'Editar {customer.name}'})

@login_required
def customer_delete(request, pk):
    """Delete a customer."""
    customer = get_object_or_404(Customer, pk=pk, user=request.user)
    
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Cliente {name} eliminado.')
        return redirect('customer_list')
        
    # Render a simple delete confirmation or handled via modal/JS in list
    # For now, standard confirm page
    return render(request, 'sales/customers/delete_confirm.html', {'object': customer})

@login_required
def product_purchase_history_api(request, customer_id):
    """API to suggest products based on customer purchase history."""
    from django.db.models import Sum, Count
    customer = get_object_or_404(Customer, pk=customer_id, user=request.user)

    # Get top 5 most purchased products by this customer
    top_products = SaleItem.objects.filter(
        sale__customer=customer
    ).values(
        'product__id', 'product__name', 'product__sale_price'
    ).annotate(
        total_quantity=Sum('quantity'),
        purchase_count=Count('id')
    ).order_by('-total_quantity')[:5]

    products = []
    for p in top_products:
        if p['product__id']:
            products.append({
                'id': p['product__id'],
                'name': p['product__name'],
                'qty': p['total_quantity'],
                'price': float(p['product__sale_price'] or 0),
            })

    return JsonResponse({'products': products})
