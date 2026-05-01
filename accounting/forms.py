from django import forms
from django.forms import inlineformset_factory
from .models import JournalEntry, JournalItem, Account


class JournalEntryForm(forms.ModelForm):
    """Header form for a manual Journal Entry (asiento contable)."""

    class Meta:
        model = JournalEntry
        fields = ['date', 'description', 'reference', 'posted']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class JournalItemForm(forms.ModelForm):
    """One imputación line. Validation enforces the debit XOR credit rule."""

    class Meta:
        model = JournalItem
        fields = ['account', 'partner', 'debit', 'credit', 'description']

    def clean(self):
        cleaned = super().clean()
        debit = cleaned.get('debit') or 0
        credit = cleaned.get('credit') or 0
        if debit and credit:
            raise forms.ValidationError("Una línea no puede tener Debe y Haber a la vez.")
        if debit < 0 or credit < 0:
            raise forms.ValidationError("Los montos no pueden ser negativos.")
        return cleaned


JournalItemFormSet = inlineformset_factory(
    JournalEntry,
    JournalItem,
    form=JournalItemForm,
    fields=['account', 'partner', 'debit', 'credit', 'description'],
    extra=2,
    can_delete=True,
    min_num=2,
    validate_min=True,
)
