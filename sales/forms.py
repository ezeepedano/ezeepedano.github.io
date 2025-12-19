from django import forms
from django.forms import inlineformset_factory
from .models import Sale, SaleItem, Customer, SALE_CHANNELS
from inventory.models import Product

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Select MercadoLibre Sales Excel', widget=forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-bold file:bg-purple-50 file:text-primary hover:file:bg-purple-100'}))

class WholesaleSaleForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Cliente"
    )
    date = forms.DateTimeField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Fecha"
    )
    shipping_cost = forms.DecimalField(
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Costo de Envío ($)"
    )
    discounts = forms.DecimalField(
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Descuento ($)"
    )
    channel = forms.ChoiceField(
        choices=SALE_CHANNELS, 
        initial='WHOLESALE',
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )

    class Meta:
        model = Sale
        fields = ['date', 'customer', 'channel', 'shipping_cost', 'discounts']

class SaleItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary'}),
        required=True
    )
    quantity = forms.IntegerField(
        initial=1,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary'})
    )
    unit_price = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary'})
    )

    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']

SaleItemFormSet = inlineformset_factory(
    Sale, SaleItem, form=SaleItemForm,
    extra=1, can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm'}),
    }
)
