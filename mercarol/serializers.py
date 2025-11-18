from rest_framework import serializers
from .models import *
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from django_countries.serializer_fields import CountryField
from rest_framework.exceptions import PermissionDenied, ValidationError
from phonenumber_field.serializerfields import PhoneNumberField
from django_countries.serializer_fields import CountryField
from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_extra_fields.fields import Base64ImageField
from django.contrib.auth import get_user_model

User = get_user_model()


# 1. REGISTRATION – this one shows ALL fields in HTML form + JSON
class CustomUserCreateSerializer(UserCreateSerializer):
    phone_number = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    address = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    role = serializers.ChoiceField(
        choices=User.Roles.choices,
        default=User.Roles.CUSTOMER,
        required=False,
        help_text="Choose VENDOR or CUSTOMER"
    )

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "phone_number",
            "address",
            "role",           # ← appears in form and JSON
        )
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        # Make sure role is always set
        validated_data.setdefault("role", User.Roles.CUSTOMER)
        return super().create(validated_data)

# 2. VIEW USER (me/, list, etc.)
class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = User
        fields = (
            "id", "email", "username", "phone_number",
            "address", "profile_image", "role", "coins", "date_joined"
        )
        read_only_fields = ("id", "email", "coins", "date_joined")


class VendorSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Vendor
        fields = "__all__"  # every field is returned / accepted
        read_only_fields = (
            "id",
            "user",  # we set it in the view – never writable
            "created_at",
            "updated_at",
        )


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name","slug", "created_at", "updated_at"]
        read_only_fields = ("id", "created_at", "updated_at", "slug")

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.name = instance.name.upper()
        instance.slug = slugify(instance.name.lower())
        instance.save()
        return instance


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class VendorProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProduct
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CartItemSerializer(serializers.ModelSerializer):
    vendor_product = serializers.StringRelatedField(read_only=True)
    # If you want full product details:
    # vendor_product = VendorProductSerializer(read_only=True)

    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "cart",
            "vendor_product",
            "quantity",
            "subtotal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "cart", "subtotal", "created_at", "updated_at"]
        # extra_kwargs = {
        #     "cart": {"write_only": True},  # never expose cart id  #error
        # }

    def get_subtotal(self, obj):
        """Safe subtotal – model method may be missing."""
        try:
            return obj.subtotal()
        except Exception:
            return obj.quantity * obj.Vendor_product.price


class CartSerializer(serializers.ModelSerializer):
    Items = CartItemSerializer(many=True, read_only=True)  # related_name='Items'

    class Meta:
        model = Cart
        fields = ["id", "user", "Items", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "order", "vendor_product", "quantity", "price", "subtotal"]
        read_only_fields = ["id", "price", "subtotal"]
        extra_kwargs = {
            "order": {"write_only": True},
            "vendor_product": {"write_only": True},
        }

    def get_subtotal(self, obj):
        try:
            return obj.subtotal()
        except AttributeError:
            return obj.quantity * obj.price

    def validate_quantity(self, value):
        if not isinstance(value, int) or value <= 0:
            raise serializers.ValidationError("Quantity must be a positive integer.")
        return value

    def validate_vendor_product(self, vendor_product):
        request = self.context.get("request")
        if not request:
            return vendor_product

        user = request.user
        role = getattr(user, "role", None)

        # Only allow customers to add any product
        # Vendors should not add via API (use admin)
        if role == "CUSTOMER":
            return vendor_product

        if role == "VENDOR":
            try:
                if vendor_product.vendor.user != user:
                    raise serializers.ValidationError(
                        "You can only add your own products."
                    )
            except AttributeError:
                raise serializers.ValidationError("Invalid vendor product.")

        return vendor_product

    def validate(self, data):
        order = data.get("order")
        vendor_product = data.get("vendor_product")

        if not order:
            raise serializers.ValidationError({"order": "This field is required."})

        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError(
                "Items can only be added to pending orders."
            )

        # Ensure order belongs to the user (customer)
        request = self.context.get("request")
        if request and request.user != order.user:
            raise serializers.ValidationError(
                "You can only add items to your own order."
            )

        # Optional: ensure vendor_product is in stock
        if hasattr(vendor_product, "stock") and vendor_product.stock <= 0:
            raise serializers.ValidationError("This product is out of stock.")

        return data

    def create(self, validated_data):
        # Auto-set price from current vendor_product
        validated_data["price"] = validated_data["vendor_product"].price
        return super().create(validated_data)

class OrderSerializer(serializers.ModelSerializer):
    # 1. Explicitly define ALL complex/read-only fields here:
    items = OrderItemSerializer(many=True, read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    payment_method = serializers.CharField(source='payment.method', read_only=True)
    shipping_address = serializers.StringRelatedField(read_only=True)
    total_items = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # CRITICAL FIX 1: Define 'status' explicitly as read_only=True 
    # to override ModelSerializer's default read/write assumption.
    status = serializers.CharField(read_only=True) 
    
    # CRITICAL FIX 2: Define 'total_amount' explicitly as read_only=True 
    # (since it's usually calculated).
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)


    class Meta:
        model = Order
        fields = [
            'id', 'status', 'status_display', 'total_amount',
            'shipping_address', 'items', 'total_items',
            'payment_status', 'payment_method',
            'created_at', 'updated_at'
        ]
        
        # FINAL CLEANUP: Only include basic auto-generated fields that should be read-only.
        read_only_fields = [
            'id', 
            #'status',          # Removed, defined explicitly above
            #'total_amount',    # Removed, defined explicitly above
            #'payment_status',  # Removed, defined explicitly above
            #'payment_method',  # Removed, defined explicitly above
            'updated_at'        # Keep simple timestamps/IDs that aren't defined above
        ]

    def get_total_items(self, obj):
        return obj.items.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add human-readable time ago
        data['time_ago'] = self.get_time_ago(instance.created_at)
        return data

    def get_time_ago(self, datetime_obj):
        delta = timezone.now() - datetime_obj
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    
    
class ShippingAddressSerializer(serializers.ModelSerializer):
    phone = PhoneNumberField()
    country = CountryField()

    class Meta:
        model = ShippingAddress
        fields = [
            "id",
            "order",
            "receiver",
            "address_line",
            "city",
            "postal_address",
            "country",
            "phone",
        ]
        read_only_fields = ["id"]

    # Order must belong to the requester and be PENDING

    def validate_order(self, order: Order):
        user = self.context["request"].user

        if not user.is_staff and order.user != user:
            raise serializers.ValidationError(
                "You can only add a shipping address to your own order."
            )
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError(
                "Shipping address can only be added to a pending order."
            )
        # One address per order
        if (
            self.instance is None
            and ShippingAddress.objects.filter(order=order).exists()
        ):
            raise serializers.ValidationError(
                "This order already has a shipping address."
            )
        return order

    # Required text fields must not be blank

    def validate(self, attrs):
        required = ("receiver", "address_line", "city", "postal_address")
        for f in required:
            val = attrs.get(f, "").strip()
            if not val:
                raise serializers.ValidationError(
                    {f: f"{f.replace('_', ' ').title()} cannot be empty."}
                )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "amount",
            "method",
            "transaction_id",
            "status",
            "vendor_payment_status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "amount",
            "transaction_id",
            "status",
            "vendor_payment_status",
            "created_at",
        ]
        extra_kwargs = {"order": {"write_only": True}}

    def validate_order(self, order: Order):
        user = self.context["request"].user
        if not user.is_staff and order.user != user:
            raise serializers.ValidationError("You can only pay for your own order.")
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError(
                "Payment can only be for a pending order."
            )
        if self.instance is None and Payment.objects.filter(order=order).exists():
            raise serializers.ValidationError("This order already has a payment.")
        return order

    def validate_method(self, value):
        if value != Payment.Mode.COINS:
            raise serializers.ValidationError("Only COINS payment is supported.")
        return value

    def _order_total(self, order: Order) -> int:
        total = order.items.aggregate(total=Sum(F("quantity") * F("price")))["total"]
        return int(total) if total is not None else 0

    def validate(self, attrs):
        order = attrs["order"]
        total = self._order_total(order)
        user = self.context["request"].user

        if attrs["method"] == Payment.Mode.COINS:
            if user.coins < total:
                raise serializers.ValidationError("Insufficient coins.")

        attrs["_total"] = total
        return attrs

    def create(self, validated_data):
        total = validated_data.pop("_total")
        order = validated_data["order"]
        user = self.context["request"].user

        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)

            if validated_data["method"] == Payment.Mode.COINS:
                if locked_user.coins < total:
                    raise serializers.ValidationError("Insufficient coins.")
                locked_user.coins -= total
                locked_user.save(update_fields=["coins"])

                validated_data.update(
                    {
                        "status": Payment.Status.COMPLETED,
                        "amount": total,
                    }
                )
                Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID)

            payment = Payment.objects.create(**validated_data)
            return payment



class AuctionSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField(read_only=True)
    winner = serializers.PrimaryKeyRelatedField(read_only=True) # Assuming previous fix applied
    
    # Custom read-only fields for computed values
    current_bid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    time_left = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    total_bids = serializers.SerializerMethodField()
    highest_bidder = serializers.SerializerMethodField()
    winner_username = serializers.SerializerMethodField()
    is_watched = serializers.SerializerMethodField()
    watcher_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    
    # ADDED: Write-only field for product ID for safe creation/update
    # Replace 'Product' with your actual model class for queryset
    # product_id = serializers.PrimaryKeyRelatedField(
    #     queryset=Product.objects.all(), 
    #     write_only=True,
    #     source='product' 
    # ) 
    # NOTE: You must uncomment this if you need to CREATE or UPDATE an AuctionItem with a product ID.
    
    class Meta:
        model = AuctionItem
        fields = [
            'id', 'product', 'start_price', 'current_bid', 'reserve_price',
            'start_time', 'end_time', 'status', 'winner',
            'time_left', 'is_active', 'total_bids', 'highest_bidder', 'winner_username',
            'created_at', 'updated_at', 'is_watched','comment_count', 'watcher_count',
            # 'product_id' # Include this if you uncomment the field above
        ]
        
        # FINAL, CLEANED read_only_fields list:
        # Only fields that are NOT explicitly defined above and should be read-only.
        # All SerializerMethodFields are inherently read-only and should NOT be listed here.
        # Fields explicitly defined with read_only=True should NOT be listed here.
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'status' # Assuming 'status' is an auto-updated model field
        ]

        # CRITICAL STEP: Explicitly define the reverse relationships as read-only
        # to prevent ModelSerializer from generating conflicting write fields for them.
        extra_kwargs = {
            'bids': {'read_only': True},
            'watchers': {'read_only': True},
            'comments': {'read_only': True},
        }
   
    def get_time_left(self, obj):
        now = timezone.now()
        if obj.end_time <= now:
            return "Ended"

        delta = obj.end_time - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_is_active(self, obj):
        return obj.is_active()
    
    

    def get_total_bids(self, obj):
        return obj.bids.count()

    def get_highest_bidder(self, obj):
        bid = obj.bids.order_by('-amount').select_related('user').first()
        if bid:
            return bid.user.get_full_name() or bid.user.username
        return None

    def get_winner_username(self, obj):
        if obj.winner:
            return obj.winner.get_full_name() or obj.winner.username
        return None

    def get_is_watched(self, obj):
        user = self.context['request'].user
        if user.is_authenticated and not user.is_vendor:
            return Watchlist.objects.filter(user=user, auction=obj).exists()
        return False

    def get_watcher_count(self, obj):
        return obj.watchers.count()

    def get_comment_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()
    

    
# class BidSerializer(serializers.ModelSerializer):
#     user = serializers.StringRelatedField(read_only=True) # Already set read_only=True here
#     auction = serializers.StringRelatedField(read_only=True) # And here
#     auction_id = serializers.UUIDField(write_only=True)

#     class Meta:
#         model = Bid
#         fields = [
#             'id', 'auction', 'auction_id', 'user', 'amount', 'max_bid',
#             'created_at', 'updated_at'
#         ]
#         # FIX: Remove 'user' and 'auction' from read_only_fields
#         # as they are explicitly defined above with read_only=True.
#         read_only_fields = [
#             'id', 'created_at', 'updated_at' 
#         ]
#         extra_kwargs = {
#             'amount': {'write_only': True},
#             'max_bid': {'write_only': True},
#         }
    
#     # ... rest of the BidSerializer content

#     def validate(self, attrs):
#         amount = attrs.get('amount')
#         max_bid = attrs.get('max_bid')

#         if amount > max_bid:
#             raise serializers.ValidationError(
#                 "Bid amount cannot exceed maximum bid."
#             )
#         if amount <= 0 or max_bid <= 0:
#             raise serializers.ValidationError(
#                 "Bid amounts must be positive."
#             )
#         return attrs


#     def create(self, validated_data):
#         auction_id = validated_data.pop('auction_id')
#         user = self.context['request'].user

#         try:
#             auction = AuctionItem.objects.get(id=auction_id)
#         except AuctionItem.DoesNotExist:
#             raise serializers.ValidationError({"auction_id": "Auction not found."})

#         return Bid.objects.create(user=user, auction=auction, **validated_data)

class BidSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    auction = serializers.StringRelatedField(read_only=True)
    auction_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Bid
        fields = [
            'id', 'auction', 'auction_id', 'user', 'amount', 'max_bid',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'amount': {'write_only': True},
            'max_bid': {'write_only': True},
        }

    def validate(self, attrs):
        amount = attrs.get('amount')
        max_bid = attrs.get('max_bid')
        if amount > max_bid:
            raise serializers.ValidationError("Bid amount cannot exceed maximum bid.")
        if amount <= 0 or max_bid <= 0:
            raise serializers.ValidationError("Bid amounts must be positive.")
        return attrs

    def validate_auction_id(self, value):
        try:
            auction = AuctionItem.objects.get(id=value)
        except AuctionItem.DoesNotExist:
            raise serializers.ValidationError("Auction not found.")
        if not auction.is_active():
            raise serializers.ValidationError("Cannot bid on inactive auction.")
        return value

    def create(self, validated_data):
        return validated_data  # Let perform_create handle creation


class WatchlistSerializer(serializers.ModelSerializer):
    auction = AuctionSerializer(read_only=True)
    auction_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Watchlist
        fields = ["id", "user", "auction", "auction_id", "added_at"]
        read_only_fields = ["id", "user", "added_at"]

    def validate_auction_id(self, value):
        """
        Validate that the auction exists and is active.
        """
        try:
            auction = AuctionItem.objects.get(id=value)
        except AuctionItem.DoesNotExist:
            raise serializers.ValidationError("Auction not found.")
        if not auction.is_active():
            raise serializers.ValidationError("Cannot add inactive auction to watchlist.")
        return value

    def create(self, validated_data):
        """
        Create a watchlist item, mapping auction_id to auction.
        """
        auction_id = validated_data.pop("auction_id")
        auction = AuctionItem.objects.get(id=auction_id)  # Already validated
        return Watchlist.objects.create(auction=auction, **validated_data)


class CommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    auction_title = serializers.CharField(source="auction.product.name", read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "username",
            "auction",
            "auction_title",
            "content",
            "created_at",
            "updated_at",
            "is_deleted",
        ]
        read_only_fields = [
            "id",
            "username",
            "auction_title",
            "created_at",
            "updated_at",
            "is_deleted",
            # 'user'
        ]