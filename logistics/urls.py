from django.urls import path
from . import views

urlpatterns = [
    path('routes/', views.DeliveryRouteListView.as_view(), name='delivery_route_list'),
    path('routes/create/', views.DeliveryRouteCreateView.as_view(), name='delivery_route_create'),
    path('routes/<int:pk>/update/', views.DeliveryRouteUpdateView.as_view(), name='delivery_route_update'),
    path('routes/<int:pk>/delete/', views.DeliveryRouteDeleteView.as_view(), name='delivery_route_delete'),
    
    # API Quick Add
    path('ajax/quick-create-vehicle/', views.quick_create_vehicle, name='quick_create_vehicle'),
    path('ajax/quick-create-zone/', views.quick_create_zone, name='quick_create_zone'),
    path('ajax/quick-create-driver/', views.quick_create_driver, name='quick_create_driver'),
    path('api/availability/', views.availability_api, name='availability_api'),
]
