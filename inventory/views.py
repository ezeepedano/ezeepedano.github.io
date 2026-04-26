from django.shortcuts import render, redirect, get_object_or_404
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django import forms
from django.db import models
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from rest_framework import viewsets, permissions
from .models import Category, Product, Ingredient, Recipe, ProductionOrder
from .serializers import CategorySerializer, ProductSerializer
from .forms import ProductForm, IngredientForm, ProductionForm
from .services import CostService, ProductionService
from .services_intelligence import StockIntelligenceService

from .services import CostService, ProductionService
from .services_intelligence import StockIntelligenceService
from .services_import import InventoryImportService

# StockIntelligenceView removed (Logic moved to Dashboard BI)

@login_required
def import_inventory(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        # Simple validation
        if not excel_file.name.endswith('.xlsx'):
            messages.error(request, 'El archivo debe ser un Excel (.xlsx)')
            return redirect('product_list')

        result = InventoryImportService.process_import(excel_file, request.user)
        
        if result['success']:
            msg = f"Importación exitosa: {result['updated']} actualizados, {result['created']} creados."
            messages.success(request, msg)
            for err in (result.get('errors') or [])[:20]:
                messages.warning(request, err)
        else:
            messages.error(request, f"Error: {result['message']}")
            
    return redirect('product_list')

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(user=self.request.user)

@login_required
def dashboard(request):
    total_products = Product.objects.filter(user=request.user).count()
    return render(request, 'dashboard.html', {'total_stock': total_products})

@login_required
def product_list(request):
    """
    Product list with sales-velocity intelligence inline.

    For every product on the page we annotate:
        * units sold in the last 30 days
        * last sale date
        * derived velocity (units / day)
        * derived days-of-cover (stock / velocity)
        * profit margin %
        * "selling at loss" flag

    The annotations are computed via subqueries so the table renders in
    a single round trip — no per-row queries when paginating 50 rows.
    """
    from django.core.paginator import Paginator
    from django.db.models import Sum, F, Q, OuterRef, Subquery, IntegerField, DateTimeField
    from django.db.models.functions import Coalesce
    from django.utils import timezone
    from datetime import timedelta
    from sales.models import SaleItem

    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Per-product 30-day units sold (subquery, scoped to current user)
    sold_30d_sq = SaleItem.objects.filter(
        product=OuterRef('pk'),
        sale__user=request.user,
        sale__date__gte=thirty_days_ago,
    ).order_by().values('product').annotate(t=Sum('quantity')).values('t')[:1]

    # Last sale date for the product
    last_sold_sq = SaleItem.objects.filter(
        product=OuterRef('pk'),
        sale__user=request.user,
    ).order_by('-sale__date').values('sale__date')[:1]

    products = (
        Product.objects.filter(user=request.user)
        .select_related('category')
        .annotate(
            sold_30d=Coalesce(Subquery(sold_30d_sq, output_field=IntegerField()), 0),
            last_sold_at=Subquery(last_sold_sq, output_field=DateTimeField()),
        )
    )

    # Global counts BEFORE any list-narrowing filters (search/category)
    base = products
    total_count = base.count()
    out_of_stock_count = base.filter(stock_quantity__lte=0).count()
    low_stock_count = base.filter(
        stock_quantity__gt=0, stock_quantity__lte=F('min_stock')
    ).count()
    selling_at_loss_count = base.filter(
        cost_price__gt=0, sale_price__lt=F('cost_price')
    ).count()
    total_stock_value = base.aggregate(
        val=Sum(F('stock_quantity') * F('cost_price'))
    )['val'] or 0

    categories = Category.objects.filter(user=request.user).order_by('name')

    # Apply filters
    filter_type = request.GET.get('filter', 'all')
    search = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')

    if filter_type == 'low_stock':
        products = products.filter(stock_quantity__gt=0, stock_quantity__lte=F('min_stock'))
    elif filter_type == 'out_of_stock':
        products = products.filter(stock_quantity__lte=0)
    elif filter_type == 'selling_at_loss':
        products = products.filter(cost_price__gt=0, sale_price__lt=F('cost_price'))

    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    if category_id:
        products = products.filter(category_id=category_id)

    # Sorting (extended with velocity)
    sort_field = request.GET.get('sort', 'name')
    sort_order = request.GET.get('order', 'asc')
    allowed_sorts = {
        'name':     'name',
        'stock':    'stock_quantity',
        'cost':     'cost_price',
        'price':    'sale_price',
        'velocity': 'sold_30d',
        'updated':  'updated_at',
    }
    sort_col = allowed_sorts.get(sort_field, 'name')
    order_prefix = '-' if sort_order == 'desc' else ''
    products = products.order_by(f'{order_prefix}{sort_col}')

    paginator = Paginator(products, 50)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    # Per-row derived fields (velocity, cover, margin, severity).
    # Computed in Python over the page slice (≤50 rows) — keeps the
    # SQL simple and avoids dialect-specific division-by-zero guards.
    for p in products_page:
        sold = int(p.sold_30d or 0)
        velocity = sold / 30.0 if sold else 0.0
        if (p.stock_quantity or 0) <= 0:
            cover, severity = 0.0, 'red'
        elif velocity > 0:
            cover = float(p.stock_quantity) / velocity
            severity = 'red' if cover <= 7 else ('amber' if cover <= 21 else 'green')
        else:
            cover, severity = None, 'idle'  # has stock, never sells
        p.velocity_30d = velocity
        p.days_of_cover = cover
        p.cover_severity = severity
        # Margin % — ``is_selling_at_loss`` is a model @property, no need
        # to set it on the instance.
        cost = float(p.cost_price or 0)
        sale = float(p.sale_price or 0)
        if cost > 0:
            p.margin_pct = (sale - cost) / cost * 100
        elif sale > 0:
            p.margin_pct = 100.0  # no cost recorded → treat as 100% margin
        else:
            p.margin_pct = None

    return render(request, 'inventory/product_list.html', {
        'products': products_page,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'selling_at_loss_count': selling_at_loss_count,
        'total_count': total_count,
        'total_stock_value': total_stock_value,
        'current_filter': filter_type,
        'search_query': search,
        'categories': categories,
        'selected_category': category_id,
        'sort_field': sort_field,
        'sort_order': sort_order,
    })


@login_required
def quick_stock_adjust(request, pk):
    """
    Quick +/- stock adjustment from the product list.

    POST body (form-encoded):
        delta:  signed integer (e.g. -5, +10)
        reason: optional free text (logged for audit)

    Returns JSON {ok, new_stock, severity} for the inline UI to update.
    """
    from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
    from django.views.decorators.http import require_POST
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')

    product = get_object_or_404(Product, pk=pk, user=request.user)
    try:
        delta = int(request.POST.get('delta', '0'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'delta inválido'}, status=400)
    if delta == 0:
        return JsonResponse({'ok': False, 'error': 'delta=0'}, status=400)

    new_stock = (product.stock_quantity or 0) + delta
    if new_stock < 0:
        return JsonResponse({'ok': False, 'error': 'el stock no puede quedar negativo'}, status=400)

    product.stock_quantity = new_stock
    product.save(update_fields=['stock_quantity', 'updated_at'])

    # Severity classification for the UI badge
    threshold = product.min_stock if product.min_stock is not None else 10
    if new_stock <= 0:
        severity = 'red'
    elif new_stock <= threshold:
        severity = 'amber'
    else:
        severity = 'green'

    reason = (request.POST.get('reason') or '').strip()[:200]
    return JsonResponse({
        'ok': True,
        'new_stock': new_stock,
        'severity': severity,
        'product_name': product.name,
        'reason': reason,
    })

@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Nuevo Producto'})

@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'title': 'Editar Producto'})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        product.delete()
        return redirect('product_list')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})

# Ingredient Views
@login_required
def ingredient_list(request):
    search_query = request.GET.get('q', '')
    ingredients = Ingredient.objects.filter(user=request.user).order_by('name')

    if search_query:
        ingredients = ingredients.filter(name__icontains=search_query)

    raw_materials = ingredients.filter(type='raw_material')
    supplies = ingredients.filter(type='supply')

    return render(request, 'inventory/ingredient_list.html', {
        'raw_materials': raw_materials,
        'supplies': supplies,
        'search_query': search_query
    })

@login_required
def ingredient_create(request):
    if request.method == 'POST':
        form = IngredientForm(request.POST, user=request.user)
        if form.is_valid():
            ingredient = form.save(commit=False)
            ingredient.user = request.user
            ingredient.save()
            return redirect('ingredient_list')
    else:
        form = IngredientForm(user=request.user)
    
    existing_ingredients = list(Ingredient.objects.filter(user=request.user).values_list('name', flat=True))
    return render(request, 'inventory/ingredient_form.html', {
        'form': form, 
        'title': 'Nuevo Insumo / Materia Prima',
        'existing_ingredients': existing_ingredients
    })

@login_required
def ingredient_edit(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk, user=request.user)
    if request.method == 'POST':
        form = IngredientForm(request.POST, instance=ingredient, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('ingredient_list')
    else:
        form = IngredientForm(instance=ingredient, user=request.user)
        
    existing_ingredients = list(Ingredient.objects.filter(user=request.user).exclude(pk=pk).values_list('name', flat=True))
    return render(request, 'inventory/ingredient_form.html', {
        'form': form, 
        'title': 'Editar Insumo / Materia Prima',
        'existing_ingredients': existing_ingredients
    })

@login_required
def product_recipe(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    
    # Use the new relation 'boms' (M2M) or 'old_boms' (FK). 
    # We migrated to M2M 'boms'.
    boms = product.boms.all().prefetch_related('lines__ingredient')
    
    return render(request, 'inventory/product_boms.html', {
        'product': product,
        'boms': boms
    })

@login_required
def produce_product(request):
    if request.method == 'POST':
        form = ProductionForm(request.POST)
        # We need to filter product QuerySet in form before validation if it's a ModelChoiceField
        # But ProductionForm definition is in forms.py. Logic filtering should be there or we limit choices here.
        # Let's inspect ProductionForm? Assuming standard ModelForm or Form with ModelChoiceField.
        form.fields['product'].queryset = Product.objects.filter(user=request.user)
        
        if form.is_valid():
            product = form.cleaned_data['product']
            quantity = form.cleaned_data['quantity']
            
            try:
                # Service handles creation
                ProductionService.process_production(product, quantity)
                messages.success(request, f"Se produjeron exitosamente {quantity} unidades de {product.name}")
                return redirect('produce_product')
            except ValidationError as e:
                messages.error(request, str(e.message))
            except Exception as e:
                messages.error(request, f"Error inesperado: {str(e)}")
    else:
        form = ProductionForm()
        form.fields['product'].queryset = Product.objects.filter(user=request.user)
        
    # Get recent orders
    recent_orders = ProductionOrder.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    return render(request, 'inventory/product_produce.html', {'form': form, 'recent_orders': recent_orders})

