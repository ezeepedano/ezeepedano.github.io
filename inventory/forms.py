from django import forms
from .models import Product, Ingredient

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'description', 'net_weight', 'unit_measure', 'cost_price', 'sale_price', 'stock_quantity']
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
        }

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'type', 'unit', 'cost_per_unit', 'stock_quantity']
        widgets = {
             'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'type': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'unit': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'cost_per_unit': forms.NumberInput(attrs={'class': 'w-full pl-8 pr-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
             'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
        }

class ProductionForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
    quantity = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}))
