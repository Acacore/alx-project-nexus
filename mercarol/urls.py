from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

router.register(r"user", UserViewSet, "user")
router.register(r"vendor", VendorViewSet, "vendor")
router.register(r"category", CategoryViewSet, "category")
router.register(r"product", ProductViewSet, "product")
router.register(r"vendor-product", VendorProductViewSet, "vendor-product")
router.register(r"product-variant", ProductVariantViewSet, "product-variant")
router.register(r"cart", CartViewSet, "cart")
router.register(r"order", OrderViewSet, "order")
router.register(r"order-item", OrderItemViewSet, "order-item")
router.register(r"shipping", ShippingAddressViewSet, "shipping")
router.register(r"payment", PaymentViewSet, "payment")
router.register(r"auction", AuctionItemViewSet, "auction")
router.register(r"bid", BidViewSet, "bid")
router.register(r"watchlist", WatchlistViewSet, "watchilist")
router.register(r"comment", CommentViewSet, "comment")

urlpatterns = [
    path("", default_redirect, name="name"),
    path("api/", include(router.urls)),
    
]
