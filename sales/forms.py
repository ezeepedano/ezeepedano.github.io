from django import forms
from django.forms import inlineformset_factory
from .models import Sale, SaleItem, Customer, SALE_CHANNELS
from inventory.models import Product

class UploadFileForm(forms.Form):
    file = forms.FileField(label='Select MercadoLibre Sales Excel', widget=forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-bold file:bg-purple-50 file:text-primary hover:file:bg-purple-100'}))

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'email', 'phone', 'document_number', 'tax_condition',
            'billing_name', 'billing_address', 'shipping_address',
            'city', 'state', 'is_wholesaler',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': 'correo@ejemplo.com'}),
            'phone': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': '+54 351 ...'}),
            'document_number': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'tax_condition': forms.Select(
                choices=[
                    ('', '— Seleccionar —'),
                    ('RESPONSABLE INSCRIPTO', 'Responsable Inscripto'),
                    ('MONOTRIBUTISTA', 'Monotributista'),
                    ('EXENTO', 'Exento'),
                    ('CONSUMIDOR FINAL', 'Consumidor Final'),
                    ('NO RESPONSABLE', 'No Responsable'),
                ],
                attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}
            ),
            'billing_name': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'billing_address': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'shipping_address': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': 'Dirección de entrega'}),
            'city': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'state': forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'}),
            'is_wholesaler': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-primary focus:ring-primary border-gray-300 rounded'}),
        }
        labels = {
            'name': 'Nombre / Razón Social',
            'email': 'Email',
            'phone': 'Teléfono',
            'document_number': 'CUIT / DNI',
            'tax_condition': 'Condición de IVA',
            'billing_name': 'Razón Social (Facturación)',
            'billing_address': 'Dirección Fiscal',
            'shipping_address': 'Dirección de Entrega',
            'city': 'Ciudad',
            'state': 'Provincia',
            'is_wholesaler': 'Es Mayorista',
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
    
    # Shipping Details
    shipping_option = forms.CharField(
        required=False,
        label="Opción de Envío",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': 'Ej. Andreani, OCA, Uber'})
    )
    tracking_number = forms.CharField(
        required=False,
        label="Código de Seguimiento (Tracking)",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )
    shipping_status = forms.ChoiceField(
        choices=[
            ('pending', 'Pendiente'),
            ('ready_to_ship', 'Listo para enviar'),
            ('shipped', 'Enviado'),
            ('delivered', 'Entregado'),
            ('cancelled', 'Cancelado'),
            ('returned', 'Devuelto')
        ],
        required=False,
        label="Estado del Envío",
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )

    # Address Fields (For Map)
    buyer_address = forms.CharField(
        required=False, 
        label="Dirección de Entrega",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary', 'placeholder': 'Calle y número'})
    )
    city = forms.CharField(
        required=False, 
        label="Ciudad",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )
    province = forms.CharField(
        required=False, 
        label="Provincia",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
    )
    zip_code = forms.CharField(
        required=False, 
        label="Código Postal",
        widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-primary focus:border-primary'})
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

        if self.instance.pk:
            if self.instance.date:
                self.initial['date'] = self.instance.date.strftime('%Y-%m-%d')
            if self.instance.due_date:
                self.initial['due_date'] = self.instance.due_date.strftime('%Y-%m-%d')
            elif self.instance.payment_status in ('PENDING', 'PARTIAL'):
                # Legacy sales sometimes carry a PENDING status without a
                # due_date. The model.clean() then refuses every save and
                # the user sees the page reload with no apparent reason.
                # Pre-fill the form with sale_date + 30 days so the field
                # is populated and submission goes through; the user can
                # still override it before saving.
                from datetime import timedelta
                base = self.instance.date.date() if hasattr(self.instance.date, 'date') else self.instance.date
                if base is not None:
                    self.initial['due_date'] = (base + timedelta(days=30)).strftime('%Y-%m-%d')

            # Try to populate payment_account from CashMovement
            from django.contrib.contenttypes.models import ContentType
            from finance.models import CashMovement

            ct = ContentType.objects.get_for_model(Sale)
            movement = CashMovement.objects.filter(content_type=ct, object_id=self.instance.pk).first()
            if movement:
                self.initial['payment_account'] = movement.account

    def clean(self):
        """
        Auto-fill ``due_date`` if the user kept payment_status =
        PENDING/PARTIAL but didn't explicitly set a date. We default to
        sale_date + 30 days. This keeps the model.clean() validator
        happy without forcing the user to manually fix every legacy
        sale they edit.
        """
        cleaned = super().clean()
        ps = cleaned.get('payment_status')
        if ps in ('PENDING', 'PARTIAL') and not cleaned.get('due_date'):
            from datetime import timedelta
            base = cleaned.get('date') or (self.instance.date if self.instance.pk else None)
            if base is not None:
                base = base.date() if hasattr(base, 'date') else base
                cleaned['due_date'] = base + timedelta(days=30)
                # Also surface the value on instance so the model's clean()
                # passes when called by save().
                self.instance.due_date = cleaned['due_date']
        return cleaned

    class Meta:
        model = Sale
        fields = [
            'date', 'customer', 'channel', 'shipping_cost', 'discounts', 
            'payment_status', 'paid_amount', 'payment_method', 'due_date',
            'shipping_option', 'tracking_number', 'shipping_status',
            'buyer_address', 'city', 'province', 'zip_code'
        ]

class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name

class SaleItemForm(forms.ModelForm):
    # ── All three fields are required=False at the field level so that
    # Django's formset machinery treats truly-empty extra rows as blank
    # and skips them.  We enforce "all-or-nothing" in clean() below.
    product = ProductChoiceField(
        queryset=Product.objects.filter(stock_quantity__gt=0).order_by('name'),
        widget=forms.Select(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary'}),
        required=False,
    )
    quantity = forms.IntegerField(
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary',
            'placeholder': '1',
        }),
    )
    unit_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:ring-primary focus:border-primary',
            'placeholder': '0.00',
        }),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(SaleItemForm, self).__init__(*args, **kwargs)
        if user:
            # Include ALL user products (not just in-stock) so that existing
            # sale items whose product now has 0 stock still validate.
            self.fields['product'].queryset = Product.objects.filter(user=user).order_by('name')

    def clean(self):
        """All-or-nothing validation: if any field has data, all are required."""
        cleaned = super().clean()
        product = cleaned.get('product')
        quantity = cleaned.get('quantity')
        unit_price = cleaned.get('unit_price')
        has_any = product or quantity or unit_price is not None

        # If this is a completely blank extra row, skip validation
        if not has_any and not self.instance.pk:
            return cleaned

        # If the row has data (or is an existing item), enforce required
        errors = {}
        if not product:
            errors['product'] = 'Este campo es requerido.'
        if not quantity:
            errors['quantity'] = 'Este campo es requerido.'
        if unit_price is None:
            errors['unit_price'] = 'Este campo es requerido.'
        if errors:
            raise forms.ValidationError(errors)
        return cleaned

    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']

SaleItemFormSet = inlineformset_factory(
    Sale, SaleItem, form=SaleItemForm,
    extra=1, can_delete=True
)
