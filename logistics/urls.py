from django.urls import path
from . import views

urlpatterns = [
    path('routes/', views.DeliveryRouteListView.as_view(), name='delivery_route_list'),
    path('routes/create/', views.DeliveryRouteCreateView.as_view(), name='delivery_route_create'),
    path('routes/<int:pk>/update/', views.DeliveryRouteUpdateView.as_view(), name='delivery_route_update'),
]
