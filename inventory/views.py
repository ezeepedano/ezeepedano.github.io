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
            if result.get('errors'):
                msg += f" Hubo {len(result['errors'])} errores no fatales."
            messages.success(request, msg)
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
    from django.core.paginator import Paginator
    from django.db.models import Sum, F

    # Base queryset
    products = Product.objects.filter(user=request.user).select_related('category')

    # Calculate counts globally before filtering the list
    total_count = products.count()
    low_stock_count = products.filter(stock_quantity__gt=0, stock_quantity__lte=10).count()
    out_of_stock_count = products.filter(stock_quantity__lte=0).count()
    total_stock_value = products.aggregate(
        val=Sum(F('stock_quantity') * F('cost_price'))
    )['val'] or 0

    # Get categories for filter dropdown
    categories = Category.objects.filter(user=request.user).order_by('name')

    # Apply filters
    filter_type = request.GET.get('filter', 'all')
    search = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')

    if filter_type == 'low_stock':
        products = products.filter(stock_quantity__gt=0, stock_quantity__lte=10)
    elif filter_type == 'out_of_stock':
        products = products.filter(stock_quantity__lte=0)

    if search:
        products = products.filter(
            models.Q(name__icontains=search) |
            models.Q(sku__icontains=search)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    # Sorting
    sort_field = request.GET.get('sort', 'name')
    sort_order = request.GET.get('order', 'asc')
    allowed_sorts = {'name': 'name', 'stock': 'stock_quantity', 'cost': 'cost_price', 'price': 'sale_price'}
    sort_col = allowed_sorts.get(sort_field, 'name')
    order_prefix = '-' if sort_order == 'desc' else ''
    products = products.order_by(f'{order_prefix}{sort_col}')

    paginator = Paginator(products, 50)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    return render(request, 'inventory/product_list.html', {
        'products': products_page,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
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

