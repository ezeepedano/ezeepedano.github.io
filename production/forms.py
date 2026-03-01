from django import forms
from django.forms import inlineformset_factory
from .models import ProductionOrder, BillOfMaterial, BomLine


class CleanNumberInput(forms.NumberInput):
    """NumberInput that strips trailing zeros: 7.0000 → 7, 7.50 → 7.5."""
    def format_value(self, value):
        if value is None or value == '':
            return ''
        try:
            return '{:g}'.format(float(value))
        except (TypeError, ValueError):
            return value

class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = ['product', 'quantity_to_produce', 'bom', 'start_date', 'end_date', 'status', 'origin']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'bom': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'quantity_to_produce': forms.NumberInput(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'status': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'origin': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
        }
        labels = {
            'product': 'Producto a Fabricar',
            'bom': 'Fórmula / Receta',
            'quantity_to_produce': 'Cantidad',
            'start_date': 'Fecha Inicio',
            'end_date': 'Fecha Fin',
            'origin': 'Documento de Origen',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        status = cleaned_data.get('status')

        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError({
                    'start_date': "La fecha de inicio no puede ser posterior a la fecha de fin.",
                    'end_date': "La fecha de fin debe ser posterior a la fecha de inicio."
                })
        
        # Require End Date if Status is Finalized
        if status == 'DONE' and not end_date:
            raise forms.ValidationError({
                'end_date': "Debe indicar una Fecha de Fin para finalizar la orden."
            })
        
        # Validate that end_date is not ridiculous (e.g. year 3000) if desired
        # or simple sanity check
        if end_date and end_date.year > 2100:
             raise forms.ValidationError({'end_date': "El año es demasiado lejano."})
             
        return cleaned_data

class BillOfMaterialForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterial
    class Meta:
        model = BillOfMaterial
        fields = ['name', 'products', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'products': forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-2'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300 text-primary focus:ring-primary'}),
        }
        labels = {
            'name': 'Nombre de la Fórmula',
            'products': 'Productos que usan esta fórmula',
            'is_active': 'Activa',
        }

# Custom form for BomLine rows — controls decimal display precisely
class BomLineForm(forms.ModelForm):
    quantity = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=CleanNumberInput(attrs={
            'class': 'w-full rounded-lg border border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20',
            'placeholder': '%',
            'step': '0.01',
        })
    )
    scrap_factor = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=CleanNumberInput(attrs={
            'class': 'w-full rounded-lg border border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20',
            'placeholder': '%',
            'step': '0.01',
        })
    )

    class Meta:
        model = BomLine
        fields = ['ingredient', 'quantity', 'scrap_factor']
        widgets = {
            'ingredient': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-slate-200 text-sm focus:border-primary focus:ring focus:ring-primary/20'
            }),
        }

# Inline FormSet for Lines
BomLineFormSet = inlineformset_factory(
    BillOfMaterial,
    BomLine,
    form=BomLineForm,
    extra=1,
    can_delete=True,
)
