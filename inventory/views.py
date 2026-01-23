from django.shortcuts import render, redirect, get_object_or_404
from django.forms import inlineformset_factory
from django import forms
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
    products = Product.objects.filter(user=request.user).select_related('category')
    low_stock_count = products.filter(stock_quantity__lte=10).count()
    return render(request, 'inventory/product_list.html', {
        'products': products,
        'low_stock_count': low_stock_count
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
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save(commit=False)
            ingredient.user = request.user
            ingredient.save()
            return redirect('ingredient_list')
    else:
        form = IngredientForm()
    return render(request, 'inventory/ingredient_form.html', {'form': form, 'title': 'Nuevo Insumo / Materia Prima'})

@login_required
def ingredient_edit(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk, user=request.user)
    if request.method == 'POST':
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            form.save()
            return redirect('ingredient_list')
    else:
        form = IngredientForm(instance=ingredient)
    return render(request, 'inventory/ingredient_form.html', {'form': form, 'title': 'Editar Insumo / Materia Prima'})

@login_required
def product_recipe(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    
    # Base attributes for widgets
    widget_attrs = {'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}
    
    # Define FormSet Class
    RecipeFormSet = inlineformset_factory(Product, Recipe, fields=('ingredient', 'quantity'), extra=1, can_delete=True,
                                        widgets={
                                            'ingredient': forms.Select(attrs=widget_attrs),
                                            'quantity': forms.NumberInput(attrs=widget_attrs),
                                        })

    if request.method == 'POST':
        # Initialize both formsets with POST data
        formula_formset = RecipeFormSet(request.POST, instance=product, prefix='formula')
        supply_formset = RecipeFormSet(request.POST, instance=product, prefix='supplies')
        
        if formula_formset.is_valid() and supply_formset.is_valid():
            # Create instances but don't commit yet to assign user
            formula_instances = formula_formset.save(commit=False)
            for instance in formula_instances:
                instance.user = request.user
                instance.save()
            # Handle deletions
            for obj in formula_formset.deleted_objects:
                obj.delete()

            supply_instances = supply_formset.save(commit=False)
            for instance in supply_instances:
                instance.user = request.user
                instance.save()
            for obj in supply_formset.deleted_objects:
                obj.delete()
            
            # --- Automatic Cost Calculation via Service ---
            total_product_cost, final_formula_cost, total_supply_cost = CostService.update_product_cost(product)
            
            messages.success(request, f"Receta guardada. Costo actualizado: ${total_product_cost:,.2f} (Formula: ${final_formula_cost:,.2f}, Insumos: ${total_supply_cost:,.2f})")
            return redirect('product_list')
    else:
        # Initialize formsets with specific querysets FILTERED BY USER
        formula_formset = RecipeFormSet(instance=product, prefix='formula', queryset=Recipe.objects.filter(ingredient__type='raw_material', user=request.user))
        supply_formset = RecipeFormSet(instance=product, prefix='supplies', queryset=Recipe.objects.filter(ingredient__type='supply', user=request.user))

    # Restrict dropdowns for each formset
    user_ingredients = Ingredient.objects.filter(user=request.user)
    
    for form in formula_formset.forms:
        form.fields['ingredient'].queryset = user_ingredients.filter(type='raw_material')
    formula_formset.empty_form.fields['ingredient'].queryset = user_ingredients.filter(type='raw_material')

    for form in supply_formset.forms:
        form.fields['ingredient'].queryset = user_ingredients.filter(type='supply')
    supply_formset.empty_form.fields['ingredient'].queryset = user_ingredients.filter(type='supply')
    
    return render(request, 'inventory/product_recipe.html', {
        'formula_formset': formula_formset, 
        'supply_formset': supply_formset, 
        'product': product
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

