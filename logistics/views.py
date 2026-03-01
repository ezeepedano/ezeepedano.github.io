from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import DeliveryRoute
from .forms import DeliveryRouteForm

class DeliveryRouteListView(LoginRequiredMixin, ListView):
    model = DeliveryRoute
    template_name = 'logistics/route_list.html'
    context_object_name = 'routes'
    ordering = ['-date']

    def get_queryset(self):
        # Return all routes (shared)
        return DeliveryRoute.objects.all()

class DeliveryRouteCreateView(LoginRequiredMixin, CreateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('delivery_route_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch sales not yet assigned to a pending/delivered stop
        # Assuming we want to ship sales that are not fully shipped.
        # For simplicity, we filter out sales that have 'active' stops.
        from sales.models import Sale
        from django.db.models import Count, Q
        
        # Get sales that don't have pending or delivered stops
        context['pending_sales'] = Sale.objects.filter(user=self.request.user).annotate(
            active_stops_count=Count('delivery_stops', filter=Q(delivery_stops__status__in=['PENDING', 'DELIVERED']))
        ).filter(active_stops_count=0).order_by('-date')
        
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user 
        response = super().form_valid(form)
        
        # Process selected sales
        selected_sales_ids = self.request.POST.getlist('selected_sales')
        if selected_sales_ids:
            from .models import DeliveryStop
            from sales.models import Sale
            
            # Simple sequence based on selection order (or just index)
            for index, sale_id in enumerate(selected_sales_ids, start=1):
                try:
                    sale = Sale.objects.get(id=sale_id)
                    DeliveryStop.objects.create(
                        route=self.object,
                        sale=sale,
                        sequence=index,
                        status='PENDING'
                    )
                except Sale.DoesNotExist:
                    continue
                    
        return response

class DeliveryRouteUpdateView(LoginRequiredMixin, UpdateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('delivery_route_list')

class DeliveryRouteDeleteView(LoginRequiredMixin, DeleteView):
    model = DeliveryRoute
    template_name = 'logistics/route_confirm_delete.html'
    success_url = reverse_lazy('delivery_route_list')


# --- QUICK MANAGE API VIEWS ---
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from .models import Vehicle, DeliveryZone
import json

@require_POST
def quick_create_vehicle(request):
    try:
        data = json.loads(request.body)
        vehicle = Vehicle.objects.create(
            user=request.user,
            name=data.get('name'),
            plate=data.get('plate'),
            capacity_volume=data.get('capacity_volume', 0),
            capacity_weight=data.get('capacity_weight', 0)
        )
        return JsonResponse({'id': vehicle.id, 'label': str(vehicle), 'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
def quick_create_zone(request):
    try:
        data = json.loads(request.body)
        zone = DeliveryZone.objects.create(
            user=request.user,
            name=data.get('name'),
            code=data.get('code'),
            description=data.get('description', '')
        )
        return JsonResponse({'id': zone.id, 'label': str(zone), 'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
def quick_create_driver(request):
    try:
        # Create a basic user with random password/username if needed
        data = json.loads(request.body)
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        
        if not first_name or not last_name:
             return JsonResponse({'status': 'error', 'message': 'Nombre y Apellido requeridos'}, status=400)

        # Generate unique username
        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@propelerp.local", # Placeholder
            password='Password123!' 
        )
        
        return JsonResponse({'id': user.id, 'label': f"{user.first_name} {user.last_name}", 'status': 'success'})
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
    available_drivers = User.objects.filter(id__in=request.user.id).exclude(id__in=assigned_driver_ids)  # Simplified, adjust based on your driver model
    
    data = {
        'date': date_str,
        'available_vehicles': [{'id': v.id, 'name': v.name} for v in available_vehicles],
        'available_drivers': [{'id': d.id, 'name': f"{d.first_name} {d.last_name}"} for d in available_drivers],
        'assigned_count': routes_on_date.count()
    }
    
    return JsonResponse(data)

