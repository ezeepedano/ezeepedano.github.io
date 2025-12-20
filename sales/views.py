from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .forms import UploadFileForm, WholesaleSaleForm, SaleItemFormSet, CustomerForm
from .services.importer import process_sales_file
from .models import Sale, Customer, CustomerStats


@login_required
def wholesale_create(request):
    """Create a new manual wholesale sale."""
    if request.method == 'POST':
        form = WholesaleSaleForm(request.POST)
        formset = SaleItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            sale = form.save(commit=False)
            sale.user = request.user
            # Generate a unique order ID for manual sales if not provided
            # Format: WH-{YYYYMMDD}-{Random/Sequence}
            if not sale.order_id:
                import uuid
                sale.order_id = f"WH-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            
            # Helper to calc total
            sale.total = 0 # Will update after items
            sale.status = 'COMPLETED' # Default for manual entry
            sale.save()
            
            # Save items
            items = formset.save(commit=False)
            total_products = 0
            for item in items:
                item.sale = sale
                item.product_title = item.product.name if item.product else "Unknown Product"
                item.sku = item.product.sku if item.product else ""
                item.save()
                total_products += item.quantity * item.unit_price
                
            # Update totals
            sale.product_revenue = total_products
            sale.total = total_products + sale.shipping_cost - sale.discounts
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
            
        form = WholesaleSaleForm(initial=initial_data)
        formset = SaleItemFormSet()
        
    return render(request, 'sales/wholesale_form.html', {'form': form, 'formset': formset})


@login_required
def sales_dashboard(request):
    """Main sales listing page."""
    channel = request.GET.get('channel')
    
    sales = Sale.objects.filter(user=request.user).select_related('customer').order_by('-date')
    
    if channel:
        sales = sales.filter(channel=channel)
        
    last_updated = Sale.objects.filter(user=request.user).latest('updated_at').updated_at if sales.exists() else None
    
    return render(request, 'sales/dashboard.html', {
        'sales': sales, 
        'last_updated': last_updated,
        'current_channel': channel
    })


@login_required
def sale_detail(request, pk):
    """Individual sale detail page."""
    sale = get_object_or_404(Sale.objects.filter(user=request.user).select_related('customer'), pk=pk)
    return render(request, 'sales/detail.html', {'sale': sale})


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
                msg = f"Processed! New Sales: {result['new_sales']}, Updated: {result['existing_sales']}, Errors: {result['errors']}"
                if result.get('customers_created'):
                    msg += f", Customers: {result['customers_created']}"
                if result['products_not_found']:
                    msg += f", Products not found: {len(result['products_not_found'])}"
                messages.success(request, msg)
                
            return redirect('sales_dashboard')
    else:
        form = UploadFileForm()
    return render(request, 'sales/upload.html', {'form': form})


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
                return redirect(f"{reverse('wholesale_create')}?customer={customer.id}")
            return redirect('customer_list')
    else:
        form = CustomerForm()
    
    return render(request, 'sales/customers/form.html', {'form': form})


@login_required
def customer_detail(request, pk):
    """
    Customer detail/dashboard page.
    """
    customer = get_object_or_404(
        Customer.objects.filter(user=request.user).select_related('stats'),
        pk=pk
    )
    
    # Get customer's sales history
    sales = Sale.objects.filter(customer=customer).order_by('-date')
    
    # Get top products (most frequently bought)
    from django.db.models import Sum
    from .models import SaleItem
    
    top_products = (
        SaleItem.objects
        .filter(sale__customer=customer)
        .values('product_title', 'sku')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:5]
    )
    
    context = {
        'customer': customer,
        'stats': getattr(customer, 'stats', None),
        'sales': sales,
        'top_products': top_products,
    }
    
    return render(request, 'sales/customers/detail.html', context)
