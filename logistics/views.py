from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import models
from .models import DeliveryRoute
from .forms import DeliveryRouteForm

class DeliveryRouteListView(LoginRequiredMixin, ListView):
    model = DeliveryRoute
    template_name = 'logistics/route_list.html'
    context_object_name = 'routes'
    ordering = ['-date']

    def get_queryset(self):
        # Tenant scope: each user only sees their own routes.
        return DeliveryRoute.objects.filter(user=self.request.user).order_by('-date')

class DeliveryRouteCreateView(LoginRequiredMixin, CreateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('delivery_route_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Tenant scope: only show this user's vehicles/zones; drivers = system users.
        from .models import Vehicle, DeliveryZone
        from django.contrib.auth.models import User
        form.fields['vehicle'].queryset = Vehicle.objects.filter(user=self.request.user)
        form.fields['zone'].queryset = DeliveryZone.objects.filter(user=self.request.user)
        form.fields['driver'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from sales.models import Sale
        from django.db.models import Count, Q

        # Sales without active delivery stops (PENDING/DELIVERED).
        sales = (Sale.objects
                 .filter(user=self.request.user)
                 .select_related('customer')
                 .annotate(active_stops=Count('delivery_stops', filter=Q(delivery_stops__status__in=['PENDING', 'DELIVERED'])))
                 .filter(active_stops=0)
                 .order_by('-date'))
        context['pending_sales'] = sales
        context['pending_sales_count'] = sales.count()
        context['pending_sales_total'] = sales.aggregate(t=models.Sum('total'))['t'] or 0

        # Vehicle capacity map for live JS calc.
        import json
        from .models import Vehicle
        vehicles = Vehicle.objects.filter(user=self.request.user)
        capacity_map = {
            str(v.id): {'volume': float(v.capacity_volume or 0), 'weight': float(v.capacity_weight or 0), 'plate': v.plate}
            for v in vehicles
        }
        context['vehicle_capacity_map_json'] = json.dumps(capacity_map)
        # Existing route assignments for date-conflict warning (JSON for JS).
        assignments = [
            {'id': r.id, 'date': r.date.isoformat() if r.date else None, 'vehicle_id': r.vehicle_id, 'driver_id': r.driver_id}
            for r in DeliveryRoute.objects.all().only('id', 'date', 'vehicle_id', 'driver_id')
        ]
        context['route_assignments_json'] = json.dumps(assignments)
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)

        selected_sales_ids = self.request.POST.getlist('selected_sales')
        if selected_sales_ids:
            from .models import DeliveryStop
            from sales.models import Sale
            for index, sale_id in enumerate(selected_sales_ids, start=1):
                try:
                    sale = Sale.objects.get(id=sale_id, user=self.request.user)
                    DeliveryStop.objects.create(
                        route=self.object,
                        sale=sale,
                        sequence=index,
                        status='PENDING',
                    )
                except Sale.DoesNotExist:
                    continue

        from django.contrib import messages
        messages.success(self.request, f"Hoja de ruta creada con {len(selected_sales_ids)} parada{'s' if len(selected_sales_ids) != 1 else ''}.")
        return response

class DeliveryRouteUpdateView(LoginRequiredMixin, UpdateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('delivery_route_list')

    def get_queryset(self):
        # Tenant scope: a user can only edit their own routes.
        return DeliveryRoute.objects.filter(user=self.request.user)


class DeliveryRouteDeleteView(LoginRequiredMixin, DeleteView):
    model = DeliveryRoute
    template_name = 'logistics/route_confirm_delete.html'
    success_url = reverse_lazy('delivery_route_list')

    def get_queryset(self):
        # Tenant scope: a user can only delete their own routes.
        return DeliveryRoute.objects.filter(user=self.request.user)


# --- QUICK MANAGE API VIEWS ---
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Vehicle, DeliveryZone
import json

@login_required
@require_POST
def quick_create_vehicle(request):
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        plate = (data.get('plate') or '').strip().upper()
        if not name or not plate:
            return JsonResponse({'status': 'error', 'message': 'Nombre y patente son obligatorios.'}, status=400)
        if Vehicle.objects.filter(plate=plate).exists():
            return JsonResponse({'status': 'error', 'message': f'Ya existe un vehículo con patente {plate}.'}, status=400)
        vehicle = Vehicle.objects.create(
            user=request.user,
            name=name,
            plate=plate,
            capacity_volume=data.get('capacity_volume') or 0,
            capacity_weight=data.get('capacity_weight') or 0,
        )
        return JsonResponse({'id': vehicle.id, 'label': str(vehicle), 'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def quick_create_zone(request):
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        code = (data.get('code') or '').strip().upper()
        if not name or not code:
            return JsonResponse({'status': 'error', 'message': 'Nombre y código son obligatorios.'}, status=400)
        if DeliveryZone.objects.filter(code=code).exists():
            return JsonResponse({'status': 'error', 'message': f'Ya existe una zona con código {code}.'}, status=400)
        zone = DeliveryZone.objects.create(
            user=request.user,
            name=name,
            code=code,
            description=(data.get('description') or '').strip(),
        )
        return JsonResponse({'id': zone.id, 'label': str(zone), 'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def quick_create_driver(request):
    try:
        data = json.loads(request.body)
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        if not first_name or not last_name:
             return JsonResponse({'status': 'error', 'message': 'Nombre y apellido requeridos.'}, status=400)

        base_username = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Generate a secure random initial password. Never log it; only return
        # it once in the JSON response so the admin can hand it to the driver.
        import secrets
        initial_password = secrets.token_urlsafe(16)

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@propelerp.local",
            password=initial_password,
        )
        # Inactive until manually activated by an admin.
        user.is_active = False
        user.save(update_fields=['is_active'])

        return JsonResponse({
            'id': user.id,
            'label': f"{user.first_name} {user.last_name}",
            'status': 'success',
            'initial_password': initial_password,
            'is_active': False,
            'note': 'Usuario creado inactivo. Active manualmente desde el panel.',
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

from django.contrib.auth.decorators import login_required

@login_required
def availability_api(request):
    """API to get available vehicles and drivers for a specific date."""
    from datetime import datetime
    date_str = request.GET.get('date')
    
    if not date_str:
        return JsonResponse({'error': 'Date parameter required'}, status=400)
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Get routes on this date
    routes_on_date = DeliveryRoute.objects.filter(date=target_date)
    
    # Get vehicles & drivers already assigned
    assigned_vehicle_ids = routes_on_date.values_list('vehicle_id', flat=True)
    assigned_driver_ids = routes_on_date.values_list('driver_id', flat=True)
    
    # Get available ones (not assigned)
    from .models import Vehicle
    from django.contrib.auth.models import User
    
    available_vehicles = Vehicle.objects.filter(user=request.user).exclude(id__in=assigned_vehicle_ids)
    available_drivers = User.objects.filter(id=request.user.id).exclude(id__in=assigned_driver_ids)
    
    data = {
        'date': date_str,
        'available_vehicles': [{'id': v.id, 'name': v.name} for v in available_vehicles],
        'available_drivers': [{'id': d.id, 'name': f"{d.first_name} {d.last_name}"} for d in available_drivers],
        'assigned_count': routes_on_date.count()
    }
    
    return JsonResponse(data)

