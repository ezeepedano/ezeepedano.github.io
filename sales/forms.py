from django import forms
from django.forms import inlineformset_factory
from .models import Sale, SaleItem, Customer, SALE_CHANNELS
from inventory.models import Product

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Select MercadoLibre Sales Excel', widget=forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-bold file:bg-purple-50 file:text-primary hover:file:bg-purple-100'}))

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'document_number', 'billing_name', 'billing_address', 'city', 'state', 'is_wholesaler']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'document_number': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'billing_name': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'billing_address': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'city': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'state': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'is_wholesaler': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-primary focus:ring-primary border-gray-300 rounded'}),
        }
        labels = {
            'name': 'Nombre / Razón Social',
            'document_number': 'CUIT / DNI',
            'billing_name': 'Nombre Facturación',
            'billing_address': 'Dirección',
            'city': 'Ciudad',
            'state': 'Provincia',
            'is_wholesaler': 'Es Mayorista'
        }

class SaleForm(forms.ModelForm):
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
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )
    # Financial Fields
    payment_status = forms.ChoiceField(
        choices=[('PENDING', 'Pendiente'), ('PARTIAL', 'Parcial'), ('PAID', 'Pagado')],
        initial='PAID',
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Estado de Cobro"
    )
    paid_amount = forms.DecimalField(
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Monto Cobrado ($)"
    )
    payment_method = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': 'Ej. Efectivo, Mercado Pago'}),
        label="Medio de Pago"
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
        label="Fecha de Vencimiento"
    )
    payment_account = forms.ModelChoiceField(
        queryset=None, # Set in init
        required=False,
        label="Cuenta de Destino (Para Caja Real)",
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(SaleForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['customer'].queryset = Customer.objects.filter(user=user).order_by('name')
            # Import Account here to avoid circular import at top if necessary, or just move import to top if safe.
            # finance.models imports User, which is fine. sales.models imports User. Mutual dependency unlikely unless models import each other.
            from finance.models import Account
            self.fields['payment_account'].queryset = Account.objects.filter(user=user, is_active=True)

    class Meta:
        model = Sale
        fields = ['date', 'customer', 'channel', 'shipping_cost', 'discounts', 'payment_status', 'paid_amount', 'payment_method', 'due_date']

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
