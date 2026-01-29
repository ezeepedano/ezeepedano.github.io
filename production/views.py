from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db import transaction
from .models import ProductionOrder, BillOfMaterial
from .forms import ProductionOrderForm, BillOfMaterialForm, BomLineFormSet

# --- Production Orders ---

class ProductionOrderListView(LoginRequiredMixin, ListView):
    model = ProductionOrder
    template_name = 'production/order_list.html'
    context_object_name = 'orders'
    ordering = ['-created_at']

    def get_queryset(self):
        # Return all orders (shared)
        return ProductionOrder.objects.all()

class ProductionOrderCreateView(LoginRequiredMixin, CreateView):
    model = ProductionOrder
    form_class = ProductionOrderForm
    template_name = 'production/order_form.html'
    success_url = reverse_lazy('production_order_list')

    def form_valid(self, form):
        # Assign current user as creator (optional, if using SET_NULL)
        form.instance.user = self.request.user 
        return super().form_valid(form)

class ProductionOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductionOrder
    form_class = ProductionOrderForm
    template_name = 'production/order_form.html'
    success_url = reverse_lazy('production_order_list')

def get_boms_for_product(request):
    product_id = request.GET.get('product_id')
    if product_id:
        boms = BillOfMaterial.objects.filter(products__id=product_id, is_active=True)
        data = [{'id': b.id, 'name': str(b)} for b in boms]
        return JsonResponse({'boms': data})
    return JsonResponse({'boms': []})

# --- Formulas (BOMs) ---

class BillOfMaterialListView(LoginRequiredMixin, ListView):
    model = BillOfMaterial
    template_name = 'production/bom_list.html'
    context_object_name = 'boms'
    ordering = ['name']

class BillOfMaterialCreateView(LoginRequiredMixin, CreateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['lines'] = BomLineFormSet(self.request.POST)
        else:
            data['lines'] = BomLineFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context['lines']
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.user = self.request.user
            self.object.save()
            # Save M2M
            form.save_m2m() 
            
            if lines.is_valid():
                lines.instance = self.object
                lines.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)

class BillOfMaterialUpdateView(LoginRequiredMixin, UpdateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['lines'] = BomLineFormSet(self.request.POST, instance=self.object)
        else:
            data['lines'] = BomLineFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context['lines']
        with transaction.atomic():
            self.object = form.save()
            if lines.is_valid():
                lines.instance = self.object
                lines.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)
