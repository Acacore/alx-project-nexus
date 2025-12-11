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
from decimal import Decimal

User = get_user_model()



# try:
#     CATEGORY_IDS = list(Category.objects.values_list('id', flat=True))
#     VENDOR_IDS = list(Vendor.objects.values_list('id', flat=True))
#     VENDOR_PRODUCT_IDS = list(VendorProduct.objects.values_list('id', flat=True))
#     PRODUCT_IDS = list(Product.objects.values_list('id', flat=True))
#     SHIPPING_ADDRESS_IDS = list(ShippingAddress.objects.values_list('id', flat=True))
# except Exception:
#     # Fallback for when DB might not be ready during schema generation
#     CATEGORY_IDS = [] 
#     VENDOR_IDS = []
#     PRODUCT_IDS = []
#     SHIPPING_ADDRESS_IDS = []
#     VENDOR_PRODUCT_IDS = []

# @extend_schema_field({'type': 'string', 'enum': CATEGORY_IDS})  # Enum values (IDs as strings for UUIDs)
# class CategoryPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs['queryset'] = Category.objects.all()
#         super().__init__(**kwargs)

# @extend_schema_field({'type': 'string', 'enum': VENDOR_IDS})
# class VendorPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs['queryset'] = Vendor.objects.all()
#         super().__init__(**kwargs)

# @extend_schema_field({'type': 'string', 'enum': PRODUCT_IDS})  # Enum values (IDs as strings for UUIDs)
# class ProductPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs['queryset'] = Product.objects.all()
#         super().__init__(**kwargs)

# @extend_schema_field({'type': 'string', 'enum': VENDOR_PRODUCT_IDS})  # Enum values (IDs as strings for UUIDs)
# class VendorProductPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
#     def __init__(self, **kwargs):
#         kwargs['queryset'] = VendorProduct.objects.all()
#         super().__init__(**kwargs)





# class ForeignKeyDropdownField(serializers.PrimaryKeyRelatedField):
#     """
#     A generic FK field that shows a dropdown in Swagger/OpenAPI.
#     """
#     def __init__(self, queryset, title=None, **kwargs):
#         super().__init__(queryset=queryset, **kwargs)
#         try:
#             self.enum = list(queryset.values_list('id', flat=True))
#         except Exception:
#             self.enum = []
#         self.title = title or queryset.model.__name__

#     def get_schema(self, view=None):
#         return {
#             "type": "string",
#             "enum": self.enum,
#             "title": self.title
#         }

#     def to_representation(self, value):
#         # This converts the model object to a representation for *output*.
#         # Returning str(value.id) is fine if you expect a string ID.
#         # If the PK is an integer, consider returning value.id
#         return str(value.id)





# class OneToOneDropdownField(serializers.PrimaryKeyRelatedField):
#     """
#     Reusable for OneToOne relationships.
#     Shows a dropdown of available related objects in Swagger.
#     """
#     def __init__(self, queryset, title=None, **kwargs):
#         super().__init__(queryset=queryset, **kwargs)
#         try:
#             self.enum = list(queryset.values_list('id', flat=True))
#         except Exception:
#             self.enum = []
#         self.title = title or queryset.model.__name__

#     @extend_schema_field({'type': 'string', 'enum': []})
#     def get_schema(self):
#         return {"type": "string", "enum": self.enum, "title": self.title}

#     def to_representation(self, value):
#         return str(value.id)



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
        fields = ['id', 'product', 'price', 'stock', 'is_available', 'is_active']
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
    vendor_product = VendorProductSerializer(
        read_only=True
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        required=False,  # optional in PUT requests
        allow_null=True
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

class ProductPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProduct
        fields = ["id", "vendor", "product",]  # adjust based on your model
        read_only_fields = fields


class AuctionItemPublicSerializer(serializers.ModelSerializer):
    product = ProductPublicSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = AuctionItem
        fields = [
            "id",
            "product",
            "start_price",
            "current_bid",
            "start_time",
            "end_time",
            "status",
            "status_display",
        ]
        read_only_fields = fields  # Public cannot modify anything

    def get_status_display(self, obj):
        if obj.status == obj.Status.ACTIVE:
            return "Live"
        elif obj.status == obj.Status.ENDED:
            return "Ended"
        elif obj.status == obj.Status.CANCELLED:
            return "Cancelled"
        return "Unknown"


class AuctionItemSerializer(serializers.ModelSerializer):
        
    class Meta:
        model = AuctionItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "vendor",
            "current_bid",
            "status",
            "winner",
            "created_at",
            "updated_at",
            "is_deleted",
        ]
        lookup_field = "id" 

    

    def validate(self, data):
        instance = getattr(self, "instance", None)

        # --- TIME VALIDATION ---
        start = data.get("start_time", getattr(instance, "start_time", None))
        end = data.get("end_time", getattr(instance, "end_time", None))

        if start and end and start >= end:
            raise serializers.ValidationError("End time must be after start time.")

        if end and end <= timezone.now():
            raise serializers.ValidationError("End time cannot be in the past.")

        # --- PRICE VALIDATION ---
        # Since start_price is required and validated by the ModelSerializer 
        # (assuming null=False in the Model), it should be in `data` here.
        start_price = data.get("start_price", getattr(instance, "start_price", None))
        reserve_price = data.get("reserve_price", getattr(instance, "reserve_price", None))

        # We keep the custom price logic here
        if start_price is not None and start_price <= 0:
            raise serializers.ValidationError("Start price must be positive.")

        if reserve_price is not None and start_price is not None and reserve_price < start_price:
            raise serializers.ValidationError("Reserve price cannot be less than start price.")

        # --- STATUS VALIDATION ---
        if instance and instance.status != AuctionItem.Status.ACTIVE:
            raise serializers.ValidationError("Cannot modify an auction that is not active.")

        return data

    def create(self, validated_data):
        
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            raise serializers.ValidationError("Request user not found in context.")

        # --- Step 1: Assign vendor automatically ---
        validated_data["vendor"] = request.user

        # --- Step 2: Initialize current_bid from start_price ---
        start_price = validated_data.get("start_price")

        if start_price is None:
            raise serializers.ValidationError({"start_price": "Start price must be provided."})
        
        if start_price is None:
            # If this error is hit, it suggests an issue with Model or input validation
            raise serializers.ValidationError({"start_price": "Start price must be provided."})
        validated_data["current_bid"] = start_price # This field is marked as read-only, so we set it here

        # --- Step 3: Mark VendorProduct as inactive/unavailable ---
        product = validated_data.get("product")
        if product:
            product.is_active = False
            product.save(update_fields=["is_active"])

        # --- Step 4: Create auction ---
        # Crucially, 'start_price' is now present in validated_data and will 
        # be passed to the Model's create method, resolving the IntegrityError.
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent updating auction after it has started or if not active
        if instance.has_started() or instance.status != AuctionItem.Status.ACTIVE:
            raise serializers.ValidationError(
                "You cannot edit an auction that has started, ended, or cancelled."
            )

        return super().update(instance, validated_data)


class BidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bid
        fields = ["id", "auction", "user", "amount", "max_bid", "created_at"]
        read_only_fields = ["id", "user", "auction", "created_at", ] 

    def validate(self, data):
        user = self.context["request"].user
        amount = data.get("amount")
        max_bid = data.get("max_bid", amount)

        auction = self.context.get("auction")
        if not auction:
            raise serializers.ValidationError("Auction context is required.")

        # Ensure decimals
        if not isinstance(amount, Decimal):
            amount = Decimal(amount)
        if not isinstance(max_bid, Decimal):
            max_bid = Decimal(max_bid)
        current_bid = auction.current_bid if isinstance(auction.current_bid, Decimal) else Decimal(auction.current_bid)

        # --- AUCTION STATUS ---
        if auction.is_deleted:
            raise serializers.ValidationError("Cannot bid on a deleted auction.")

        if auction.status != AuctionItem.Status.ACTIVE:
            raise serializers.ValidationError("Cannot bid on an inactive auction.")

        if not auction.has_started():
            raise serializers.ValidationError("Auction has not started yet.")

        if timezone.now() > auction.end_time:
            raise serializers.ValidationError("Auction has already ended.")

        # --- USER CHECK ---
        if auction.vendor == user:
            raise serializers.ValidationError("Vendors cannot bid on their own auctions.")

        # --- BID AMOUNT ---
        if amount <= current_bid:
            raise serializers.ValidationError(
                f"Your bid must be higher than the current bid ({current_bid})."
            )

        if max_bid < amount:
            raise serializers.ValidationError("Maximum bid cannot be less than bid amount.")

        # Minimum increment (example $1)
        min_increment = Decimal("1.00")
        if amount < current_bid + min_increment:
            raise serializers.ValidationError(
                f"Your bid must be at least {min_increment} higher than the current bid."
            )

        return data

    def create(self, validated_data):
        # Assign user from context
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class WinnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class ArchivedAuctionSerializer(serializers.ModelSerializer):
    vendor = UserSerializer(read_only=True)
    winner = UserSerializer(read_only=True)
    product = VendorProductSerializer(read_only=True)

    class Meta:
        model = ArchivedAuction
        fields = [
            "original_auction_id",
            "vendor",
            "product",
            "start_price",
            "final_bid",
            "reserve_price",
            "start_time",
            "end_time",
            "status",
            "winner",
            "archived_at",
        ]
        read_only_fields = ["archived_at"]


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
