from django import forms
from .models import Product, Recipe, ProductionOrder, Batch, Ingredient, Category

class ProductForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # min_stock has a model default of 10. Mark it optional so users
        # who don't tweak the threshold can still save the form. Empty
        # POSTs are coerced to the default in clean_min_stock.
        if 'min_stock' in self.fields:
            self.fields['min_stock'].required = False
            if not self.instance.pk:
                self.fields['min_stock'].initial = 10

    def clean_min_stock(self):
        v = self.cleaned_data.get('min_stock')
        return 10 if v in (None, '') else v

    class Meta:
        model = Product
        fields = ['sku', 'name', 'description', 'category', 'net_weight', 'unit_measure', 'cost_price', 'sale_price', 'stock_quantity', 'min_stock']
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium', 'rows': 3}),
            'net_weight': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'unit_measure': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'cost_price': forms.NumberInput(attrs={'class': 'w-full pl-8 pr-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'sale_price': forms.NumberInput(attrs={'class': 'w-full pl-8 pr-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'min_stock': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
        }

class IngredientForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # min_stock optional with sensible default (10) — same pattern as
        # ProductForm so the field can be left blank without breaking save.
        if 'min_stock' in self.fields:
            self.fields['min_stock'].required = False
            if not self.instance.pk:
                self.fields['min_stock'].initial = 10
        # Code optional too — auto-generated in save() when empty.
        if 'code' in self.fields:
            self.fields['code'].required = False

    class Meta:
        model = Ingredient
        fields = ['name', 'code', 'type', 'unit', 'cost_per_unit', 'stock_quantity', 'min_stock']
        widgets = {
             'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium', 'placeholder': 'Auto si vacío. Ej: MGS01'}),
             'type': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'unit': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'cost_per_unit': forms.NumberInput(attrs={'class': 'w-full pl-8 pr-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'min_stock': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
        }

    def clean_min_stock(self):
        v = self.cleaned_data.get('min_stock')
        from decimal import Decimal
        return Decimal('10') if v in (None, '') else v

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            qs = Ingredient.objects.filter(name__iexact=name)
            # Always scope by user. If form is built without one, refuse to
            # validate cross-tenant — better to fail loudly than to compare
            # this user's name against everyone else's.
            if self.user is None:
                raise forms.ValidationError("No se puede validar el nombre sin contexto de usuario.")
            qs = qs.filter(user=self.user)

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Ya existe un ingrediente con este nombre.")
        return name

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            return code  # save() will auto-generate
        if self.user is None:
            raise forms.ValidationError("No se puede validar el código sin contexto de usuario.")
        qs = Ingredient.objects.filter(user=self.user, code__iexact=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya tenés otro ingrediente con ese código.")
        return code

    def save(self, commit=True):
        """Auto-generate code if empty — scoped per-user."""
        instance = super().save(commit=False)

        if not instance.code:
            # Generate code from first 3 letters of name + sequence number,
            # restricted to the owning user so codes don't collide across
            # tenants and the search doesn't leak other tenants' codes.
            base_code = (instance.name or '')[:3].upper() or 'ING'
            user_for_scope = self.user or instance.user
            existing_codes = Ingredient.objects.filter(
                user=user_for_scope,
                code__startswith=base_code,
            ).values_list('code', flat=True)

            numbers = []
            for code in existing_codes:
                try:
                    num = int(code[len(base_code):])
                    numbers.append(num)
                except (ValueError, IndexError):
                    pass

            next_num = max(numbers) + 1 if numbers else 1
            instance.code = f"{base_code}{next_num:02d}"

        if commit:
           instance.save()
        return instance

class ProductionForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
    quantity = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
