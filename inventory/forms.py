from django import forms
from .models import Product, Recipe, ProductionOrder, Batch, Ingredient, Category

class ProductForm(forms.ModelForm):
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

    class Meta:
        model = Ingredient
        fields = ['name', 'code', 'type', 'unit', 'cost_per_unit', 'stock_quantity']
        widgets = {
             'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium', 'placeholder': 'Ej: MGS01'}),
             'type': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'unit': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'cost_per_unit': forms.NumberInput(attrs={'class': 'w-full pl-8 pr-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            qs = Ingredient.objects.filter(name__iexact=name)
            if self.user:
                qs = qs.filter(user=self.user)
            
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("Ya existe un ingrediente con este nombre.")
        return name
    
    def save(self, commit=True):
        """Auto-generate code if empty."""
        instance = super().save(commit=False)
        
        if not instance.code:
            # Generate code from first 3 letters of name + sequence number
            base_code = instance.name[:3].upper()
            
            # Find next available sequence
            existing_codes = Ingredient.objects.filter(code__startswith=base_code).values_list('code', flat=True)
            
            # Extract numbers from existing codes
            numbers = []
            for code in existing_codes:
                try:
                    num = int(code[len(base_code):])
                    numbers.append(num)
                except (ValueError, IndexError):
                    pass
            
            # Generate next number
            next_num = 1
            if numbers:
                next_num = max(numbers) + 1
            
            instance.code = f"{base_code}{next_num:02d}"
        
        if commit:
           instance.save()
        return instance

class ProductionForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
    quantity = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
