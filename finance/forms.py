from django import forms
from .models import FixedCost, Purchase, MonthlyExpense, Asset, Provider, AssetCategory, Account

class FixedCostForm(forms.ModelForm):
    class Meta:
        model = FixedCost
        fields = ['name', 'category', 'description', 'amount', 'due_day']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium', 'rows': 3}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
            'due_day': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent focus:bg-white focus:border-primary focus:ring-2 focus:ring-primary focus:ring-opacity-20 transition-all font-medium'}),
        }

class PurchaseForm(forms.ModelForm):
    provider = forms.ModelChoiceField(queryset=Provider.objects.all(), required=False)
    
    class Meta:
        model = Purchase
        fields = ['date', 'code', 'provider', 'category', 'description', 'amount']

class VariableExpenseForm(forms.ModelForm):
    class Meta:
        model = MonthlyExpense 
        fields = ['name', 'amount', 'due_date', 'description']

class AssetForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=AssetCategory.objects.all(), required=False)
    provider = forms.ModelChoiceField(queryset=Provider.objects.all(), required=False)

    class Meta:
        model = Asset
        fields = ['name', 'category', 'cost', 'purchase_date', 'provider', 'location', 'description']

class ProviderForm(forms.ModelForm):
    class Meta:
        model = Provider # Assumes imported
        fields = ['name', 'email', 'phone', 'address', 'city', 'cuit', 'website', 'notes']




class TransactionImportForm(forms.Form):
    file = forms.FileField(label="Archivo de Liquidación (CSV/Excel)", widget=forms.FileInput(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent'}))
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="Cuenta Destino", widget=forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-xl bg-gray-50 border-transparent'}))
