from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

router.register(r'user', UserViewSet, 'user')
router.register(r'vendor', ViendorViewSet, 'vendor')
router.register(r'category', CategoryViewSet, 'category')
router.register(r'product', ProductViewSet, 'product')
router.register(r'vendor-product', VendorProductViewset, 'vendor-product')
router.register(r'product-variant', ProductVariantViewset, 'product-variant')
router.register(r'cart', CartViewSet, 'cart')
router.register(r'order', OrderItemViewSet, 'order')
router.register(r'order-item', OrderItemViewSet, 'order-item')



urlpatterns = [
    path("home", home, name ='name' ),
    path('api/', include(router.urls))
]
