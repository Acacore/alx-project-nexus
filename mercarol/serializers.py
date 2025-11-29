from rest_framework import serializers
from .models import *
from drf_spectacular.utils import extend_schema_field
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
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

User = get_user_model()



try:
    CATEGORY_IDS = list(Category.objects.values_list('id', flat=True))
    VENDOR_IDS = list(Vendor.objects.values_list('id', flat=True))
    VENDOR_PRODUCT_IDS = list(VendorProduct.objects.values_list('id', flat=True))
    PRODUCT_IDS = list(Product.objects.values_list('id', flat=True))
    SHIPPING_ADDRESS_IDS = list(ShippingAddress.objects.values_list('id', flat=True))
except Exception:
    # Fallback for when DB might not be ready during schema generation
    CATEGORY_IDS = [] 
    VENDOR_IDS = []
    PRODUCT_IDS = []
    SHIPPING_ADDRESS_IDS = []
    VENDOR_PRODUCT_IDS = []

# @extend_schema_field({'type': 'string', 'enum': CATEGORY_IDS})  # Enum values (IDs as strings for UUIDs)
# class CategoryPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs['queryset'] = Category.objects.all()
#         super().__init__(**kwargs)

@extend_schema_field({'type': 'string', 'enum': VENDOR_IDS})
class VendorPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        kwargs['queryset'] = Vendor.objects.all()
        super().__init__(**kwargs)

@extend_schema_field({'type': 'string', 'enum': PRODUCT_IDS})  # Enum values (IDs as strings for UUIDs)
class ProductPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        kwargs['queryset'] = Product.objects.all()
        super().__init__(**kwargs)

@extend_schema_field({'type': 'string', 'enum': VENDOR_PRODUCT_IDS})  # Enum values (IDs as strings for UUIDs)
class VendorProductPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        kwargs['queryset'] = VendorProduct.objects.all()
        super().__init__(**kwargs)





class ForeignKeyDropdownField(serializers.PrimaryKeyRelatedField):
    """
    A generic FK field that shows a dropdown in Swagger/OpenAPI.
    """
    def __init__(self, queryset, title=None, **kwargs):
        super().__init__(queryset=queryset, **kwargs)
        try:
            self.enum = list(queryset.values_list('id', flat=True))
        except Exception:
            self.enum = []
        self.title = title or queryset.model.__name__

    def get_schema(self, view=None):
        return {
            "type": "string",
            "enum": self.enum,
            "title": self.title
        }

    def to_representation(self, value):
        # This converts the model object to a representation for *output*.
        # Returning str(value.id) is fine if you expect a string ID.
        # If the PK is an integer, consider returning value.id
        return str(value.id)





class OneToOneDropdownField(serializers.PrimaryKeyRelatedField):
    """
    Reusable for OneToOne relationships.
    Shows a dropdown of available related objects in Swagger.
    """
    def __init__(self, queryset, title=None, **kwargs):
        super().__init__(queryset=queryset, **kwargs)
        try:
            self.enum = list(queryset.values_list('id', flat=True))
        except Exception:
            self.enum = []
        self.title = title or queryset.model.__name__

    @extend_schema_field({'type': 'string', 'enum': []})
    def get_schema(self):
        return {"type": "string", "enum": self.enum, "title": self.title}

    def to_representation(self, value):
        return str(value.id)



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
    # logo = Base64ImageField(required=False, allow_null=True)

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
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,  
        allow_null=True
    )
    # vendor = VendorPrimaryKeyRelatedField()
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'category', 'image']
        read_only_fields = ("id", "created_at", "updated_at", "slug", "user")


    # print(VENDOR_IDS)
    #  # Use @extend_schema_field to override how the UI interprets the field
    # @extend_schema_field(field={"type": "string", "enum": CATEGORY_IDS})
    # def get_category_display(self, obj):
    #     # This method is not actually used by the API but is used to hook the schema change
    #     return obj.category.id

    # @extend_schema_field(field={"type": "string", "enum": VENDOR_IDS})
    # def get_vendor_display(self, obj):
    #     return obj.vendor.id

     # Explicitly map the field name 'category' to a unique type definition in the schema
    # Optional: Explicitly control schema enum for category and user
    # @extend_schema_field(
    #     field={
    #         "type": "string",
    #         "enum": [str(id) for id in Category.objects.values_list('id', flat=True)],
    #         "title": "Category UUID"
    #     }
    # )
    # def get_category_display(self, obj):
    #     return obj.category.id if obj.category else None

    # @extend_schema_field(
    #     field={
    #         "type": "string",
    #         "enum": [str(id) for id in Product.objects.values_list('user', flat=True)],
    #         "title": "Vendor UUID"
    #     }
    # )
    # def get_user_display(self, obj):
    #     return obj.user.id
class VendorProductSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,  # optional in PUT requests
        allow_null=True
    )

    class Meta:
        model = VendorProduct
        fields = ['id', 'product', 'price', 'stock', 'is_available']
        read_only_fields = ('id', 'created_at', 'updated_at')

    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.instance is not None:
                self.fields['product'].read_only = True

    def validate_product(self, product):
        if self.instance and self.instance.product != product:
            raise serializers.ValidationError("You cannot change the product once set.")
        return product



class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CartItemSerializer(serializers.ModelSerializer):
    vendor_product = serializers.PrimaryKeyRelatedField(
        queryset= VendorProduct.objects.all(),
        required=False,  
        allow_null=True
    ) 
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
            return obj.quantity * obj.vendor_product.price
        
    # @extend_schema_field(
    #     field={
    #         "type": "string",
    #         "enum": VENDOR_PRODUCT_IDS,
    #         "title": "VENDOR_PRODUCT UUID" # A unique title helps ensure a unique component name
    #     }
    # )
    # def get_vendor_product_display(self, obj):
    #     # This method is only for schema generation hook
    #     return obj.name.id

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)  # related_name='Items'

    class Meta:
        model = Cart
        fields = ["id", "user", "items", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()
    vendor_product = ForeignKeyDropdownField(
        queryset=VendorProduct.objects.all(),
        # Optional: customize the title in the docs
        title="Related User ID" 
    )
    order = ForeignKeyDropdownField(
        queryset=Order.objects.all(),
        # Optional: customize the title in the docs
        title="Related User ID" 
    )

    class Meta:
        model = OrderItem
        fields = ["id", 'order', "vendor_product", "quantity", "price", "subtotal"]
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
    items = OrderItemSerializer(many=True, read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    payment_method = serializers.CharField(source='payment.method', read_only=True)
    shipping_address = serializers.StringRelatedField(read_only=True)
    total_items = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%b %d, %Y %I:%M %p", read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status = serializers.CharField(read_only=True) 
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

# from drf_spectacular.utils import extend_schema_field # You'll need this import too
class ShippingAddressSerializer(serializers.ModelSerializer):
    country = CountryField(name_only=True)
    phone = PhoneNumberField()
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'user', 'delivery_note', 'address_line',
            'city', 'postal_address', 'country', 'phone',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def to_internal_value(self, data):
        new_data = {}
        for key, value in data.items():
            if isinstance(value, dict) and 'value' in value:
                new_data[key] = value['value']
            else:
                new_data[key] = value
        return super().to_internal_value(new_data)



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




# class CheckoutSerializer(serializers.Serializer):
#     shipping = serializers.PrimaryKeyRelatedField(
#         queryset=ShippingAddress.objects.all()
#     )
#     receiver = serializers.CharField(
#         required=False, allow_blank=True, max_length=255,
#         help_text="Optional note for the order"
#     )

#     def validate_shipping(self, value):
#         """
#         Ensure the shipping address exists and belongs to the user.
#         The actual validation in your view is sufficient, but you can also add here.
#         """
#         # Note: If you want strict serializer validation:
#         request = self.context.get("request")
#         user = getattr(request, "user", None)
#         if user and not ShippingAddress.objects.filter(id=value, user=user).exists():
#             raise serializers.ValidationError("Invalid shipping address for this user.")
#         return value
  
# serializers.py

# serializers.py



# @extend_schema_field(OpenApiTypes.UUID)  # or OpenApiTypes.UUID if you're using UUIDs
# @extend_schema_field({'type': 'integer', 'enum': SHIPPING_ADDRESS_IDS})
# class UserShippingField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs.setdefault("queryset", ShippingAddress.objects.none())
#         super().__init__(**kwargs)

#     def get_queryset(self):
#         request = self.context.get("request")
#         if request and request.user.is_authenticated:
#             return ShippingAddress.objects.filter(user=request.user)
#         return ShippingAddress.objects.none()

    

    @property
    def choices(self):
        """Dynamically generate choices for the current user"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            queryset = ShippingAddress.objects.filter(user=request.user)
            return {addr.id: str(addr) for addr in queryset}
        return {}

class CheckoutSerializer(serializers.Serializer):
    """
    Serializer for checkout process.
    User must select an existing shipping address.
    Payment method defaults to COINS.
    """

    shipping_address = serializers.PrimaryKeyRelatedField(
        queryset= ShippingAddress.objects.all(),
        required=False,  
        allow_null=True
    ) 

    payment_method = serializers.ChoiceField(
        choices=Payment.Mode.choices,
        default=Payment.Mode.COINS,
        required=False,
        help_text="Select a payment method. Defaults to COINS."
    )

    deliver_note = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional delivery instructions for the courier."
    )

    # def validate_shipping_address(self, value: ShippingAddress):
    #     """
    #     Ensure the selected shipping address belongs to the current user.
    #     """
    #     user = self.context['request'].user
    #     if value.user != user:
    #         raise serializers.ValidationError("You can only select your own saved addresses.")
    #     return value

    


# class AuctionItemSerializer(serializers.ModelSerializer):
#     product = serializers.StringRelatedField(read_only=True)
#     winner = serializers.PrimaryKeyRelatedField(read_only=True) # Assuming previous fix applied
#     product_id = serializers.PrimaryKeyRelatedField(
#     queryset=Product.objects.all(),
#     write_only=True,
#     source='product'
# )

#     # Custom read-only fields for computed values
#     current_bid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
#     time_left = serializers.SerializerMethodField()
#     is_active = serializers.SerializerMethodField()
#     total_bids = serializers.SerializerMethodField()
#     highest_bidder = serializers.SerializerMethodField()
#     winner_username = serializers.SerializerMethodField()
#     is_watched = serializers.SerializerMethodField()
#     watcher_count = serializers.SerializerMethodField()
#     comment_count = serializers.SerializerMethodField()
    
   
#     class Meta:
#         model = AuctionItem
#         fields = [
#             'id', 'product', 'product_id', 'start_price', 'current_bid', 'reserve_price',
#             'start_time', 'end_time', 'status', 'winner',
#             'time_left', 'is_active', 'total_bids', 'highest_bidder', 'winner_username',
#             'created_at', 'updated_at', 'is_watched','comment_count', 'watcher_count',
#         ]
    
#         read_only_fields = [
#             'id', 'created_at', 'updated_at', 'status' # Assuming 'status' is an auto-updated model field
#         ]

#         # to prevent ModelSerializer from generating conflicting write fields for them.
#         extra_kwargs = {
#             'bids': {'read_only': True},
#             'watchers': {'read_only': True},
#             'comments': {'read_only': True},
#         }
   
#     def get_time_left(self, obj):
#         now = timezone.now()
#         if obj.end_time <= now:
#             return "Ended"

#         delta = obj.end_time - now
#         days = delta.days
#         hours, remainder = divmod(delta.seconds, 3600)
#         minutes, _ = divmod(remainder, 60)

#         if days:
#             return f"{days}d {hours}h {minutes}m"
#         if hours:
#             return f"{hours}h {minutes}m"
#         return f"{minutes}m"

#     def get_is_active(self, obj):
#         return obj.is_active()
    
    

#     def get_total_bids(self, obj):
#         return obj.bids.count()

#     def get_highest_bidder(self, obj):
#         bid = obj.bids.order_by('-amount').select_related('user').first()
#         if bid:
#             return bid.user.get_full_name() or bid.user.username
#         return None

#     def get_winner_username(self, obj):
#         if obj.winner:
#             return obj.winner.get_full_name() or obj.winner.username
#         return None

#     def get_is_watched(self, obj):
#         request = self.context.get("request", None)
#         if request and request.user.is_authenticated:
#             return Watchlist.objects.filter(
#                 user=request.user, 
#                 auction=obj
#             ).exists()
#         return False


#     def get_watcher_count(self, obj):
#         return obj.watchers.count()

#     def get_comment_count(self, obj):
#         return obj.comments.filter(is_deleted=False).count()


class AuctionItemSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField(read_only=True)
    winner = serializers.PrimaryKeyRelatedField(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=VendorProduct.objects.all(),
        write_only=True,
        source='product'
    )

    current_bid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    time_left = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    total_bids = serializers.SerializerMethodField()
    highest_bidder = serializers.SerializerMethodField()
    winner_username = serializers.SerializerMethodField()
    is_watched = serializers.SerializerMethodField()
    watcher_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = AuctionItem
        fields = [
            'id', 'product', 'product_id', 'start_price', 'current_bid', 'reserve_price',
            'start_time', 'end_time', 'status', 'winner',
            'time_left', 'is_active', 'total_bids', 'highest_bidder', 'winner_username',
            'created_at', 'updated_at', 'is_watched', 'comment_count', 'watcher_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']


    def validate_product(self, product):
        if self.instance and self.instance.product == product:
            return product  # allow current product on update
        if hasattr(product, 'auction'):
            raise serializers.ValidationError("This product is already in an auction.")
        return product


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
            return bid.user.username
        return None

    def get_winner_username(self, obj):
        if obj.winner:
            return obj.winner.username
        return None

    def get_is_watched(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Watchlist.objects.filter(user=request.user, auction=obj).exists()
        return False

    def get_watcher_count(self, obj):
        return obj.watchers.count()

    def get_comment_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()


class BidSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    auction = serializers.StringRelatedField(read_only=True)


    class Meta:
        model = Bid
        fields = ['id', 'auction', 'user', 'amount', 'max_bid', 'created_at', 'updated_at']
        read_only_fields = ['id', 'auction', 'user', 'created_at', 'updated_at']
        extra_kwargs = {
            'amount': {'write_only': True},
            'max_bid': {'write_only': True},
        }


class WinnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    


class WatchlistSerializer(serializers.ModelSerializer):
    auction = AuctionItemSerializer(read_only=True)
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
        Create a watchlist item. The user will be assigned in the ViewSet.
        """
        auction_id = validated_data.pop("auction_id")
        auction = AuctionItem.objects.get(id=auction_id)
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
            "user",
            "username",
            "auction_title",
            "created_at",
            "updated_at",
            "is_deleted",
        ]

        extra_kwargs = {
            "user": {"read_only": True}  
        }
