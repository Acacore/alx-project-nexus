from rest_framework import serializers
from .models import *
from django.db import transaction
from django.db.models import Sum, F
from django_countries.serializer_fields import CountryField
from rest_framework.exceptions import PermissionDenied, ValidationError
from phonenumber_field.serializerfields import PhoneNumberField
from django_countries.serializer_fields import CountryField


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ["coins", "password"]
        read_only_fields = [
            "id",
            "is_staff",
            "is_superuser",
            "is_active",
            "date_joined",
            "last_login",
            "role",  # if exists
        ]

    def update(self, instance, validated_data):
        if "password" in validated_data:
            raise ValidationError({"password": "Password cannot be updated here."})
        return super().update(instance, validated_data)


class VendorSerializer(serializers.ModelSerializer):
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
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


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
        extra_kwargs = {
            "cart": {"write_only": True},  # never expose cart id
        }

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
