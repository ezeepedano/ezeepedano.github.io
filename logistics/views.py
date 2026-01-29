from django.views.generic import ListView, CreateView, UpdateView
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

    def form_valid(self, form):
        form.instance.user = self.request.user 
        return super().form_valid(form)

class DeliveryRouteUpdateView(LoginRequiredMixin, UpdateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('delivery_route_list')
