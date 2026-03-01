from django import forms
from .models import DeliveryRoute

class DeliveryRouteForm(forms.ModelForm):
    class Meta:
        model = DeliveryRoute
        fields = ['date', 'vehicle', 'driver', 'zone', 'status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'vehicle': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all pl-10'}),
            'driver': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all pl-10'}),
            'zone': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
            'status': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-200 focus:border-primary focus:ring focus:ring-primary/20 transition-all'}),
        }
        labels = {
            'date': 'Fecha de Reparto',
            'vehicle': 'Vehículo Asignado',
            'driver': 'Conductor',
            'zone': 'Zona de Reparto',
        }
