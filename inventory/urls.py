from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, product_list, product_create, product_edit, product_delete, ingredient_list, ingredient_create, ingredient_edit, product_recipe, produce_product, dashboard

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    # path('', dashboard, name='dashboard'), # Dashboard moved to core root
    path('', product_list, name='product_list'), # Root inventory shows list
    path('api/', include(router.urls)),
    # path('products/', product_list, name='product_list'), # Redundant
    path('products/new/', product_create, name='product_create'),
    path('products/<int:pk>/edit/', product_edit, name='product_edit'),
    path('products/<int:pk>/recipe/', product_recipe, name='product_recipe'),
    path('products/<int:pk>/delete/', product_delete, name='product_delete'),
    
    path('ingredients/', ingredient_list, name='ingredient_list'),
    path('ingredients/new/', ingredient_create, name='ingredient_create'),
    path('ingredients/<int:pk>/edit/', ingredient_edit, name='ingredient_edit'),
    
    path('production/', produce_product, name='produce_product'),
]
