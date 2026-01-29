from django import forms
from django.forms import inlineformset_factory
from .models import ProductionOrder, BillOfMaterial, BomLine

class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = ['product', 'quantity_to_produce', 'bom', 'start_date', 'end_date', 'status', 'origin']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'bom': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'quantity_to_produce': forms.NumberInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'status': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'origin': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
        }
        labels = {
            'product': 'Producto a Fabricar',
            'bom': 'Fórmula / Receta',
            'quantity_to_produce': 'Cantidad',
            'start_date': 'Fecha Inicio',
            'end_date': 'Fecha Fin',
            'origin': 'Documento de Origen',
        }

class BillOfMaterialForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterial
        fields = ['name', 'products', 'quantity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'products': forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-2'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300 text-primary focus:ring-primary'}),
        }
        labels = {
            'name': 'Nombre de la Fórmula',
            'products': 'Productos que usan esta fórmula',
            'quantity': 'Cantidad Base (%)',
            'is_active': 'Activa',
        }

# Inline FormSet for Lines
BomLineFormSet = inlineformset_factory(
    BillOfMaterial, 
    BomLine,
    fields=['ingredient', 'quantity', 'scrap_factor'],
    extra=1,
    can_delete=True,
    widgets={
        'ingredient': forms.Select(attrs={'class': 'w-full rounded-lg border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20'}),
        'quantity': forms.NumberInput(attrs={'class': 'w-full rounded-lg border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20', 'placeholder': '%'}),
        'scrap_factor': forms.NumberInput(attrs={'class': 'w-full rounded-lg border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20', 'placeholder': '%'}),
    }
)
