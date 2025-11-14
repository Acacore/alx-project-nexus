from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(User)
admin.site.register(Vendor)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(VendorProduct)
admin.site.register(ProductVariant)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingAddress)
admin.site.register(Payment)
admin.site.register(AuctionItem)
admin.site.register(Bid)
admin.site.register(Watchlist)
admin.site.register(Comment)

