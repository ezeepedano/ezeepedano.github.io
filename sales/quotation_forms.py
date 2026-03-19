"""
Forms for the Quotation / Presupuesto module.
"""
from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, QuotationItem, Customer
from inventory.models import Product


class QuotationForm(forms.ModelForm):
    """Form for Quotation header."""

    class Meta:
        model = Quotation
        fields = [
            'date', 'valid_until', 'customer', 'sale_type',
            'sale_condition', 'payment_terms', 'discount_pct',
            'notes', 'status',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'customer': forms.Select(),
            'sale_type': forms.Select(),
            'sale_condition': forms.Select(),
            'payment_terms': forms.TextInput(attrs={'placeholder': 'Ej: 30 días'}),
            'discount_pct': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Condiciones especiales, disponibilidad, etc.'}),
            'status': forms.Select(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['customer'].queryset = Customer.objects.filter(user=user).order_by('name')


class QuotationItemForm(forms.ModelForm):
    """Form for individual quotation line items."""

    class Meta:
        model = QuotationItem
        fields = ['product', 'description', 'quantity', 'unit_price', 'discount_pct', 'iva_pct']
        widgets = {
            'product': forms.Select(attrs={'class': 'product-select'}),
            'description': forms.TextInput(attrs={'placeholder': 'Descripción'}),
            'quantity': forms.NumberInput(attrs={'min': '1', 'value': '1'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'discount_pct': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100', 'value': '0'}),
            'iva_pct': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'value': '21'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['product'].queryset = Product.objects.filter(user=user).order_by('name')
        self.fields['product'].required = False


QuotationItemFormSet = inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True,
)
