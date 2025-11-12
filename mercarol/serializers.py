from rest_framework import serializers
from .models import *
from django.db import transaction
from django_countries.serializer_fields import CountryField



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['coins']


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'



class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class VendorProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProduct
        fields = '__all__'


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = '__all__'

    def validate(self, data):
        user = self.context['request'].user


        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise serializers.ValidationError(
                "No Vendor profile found for this user."
            )

        vendor_product = data.get('vendor_product')
        name = data.get('name')
        if ProductVariant.objects.filter(vendor_product_id=vendor_product.id,
            name__iexact=name).exists():
            raise serializers.ValidationError("You already created a vairant for this product")
        return data

class CartItemSerializer(serializers.ModelSerializer):
    vendor_product = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CartItem
        fields = '__all__'

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    class Meta:
        model = Cart
        fields = '__all__'



class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'vendor_product', 'quantity', 'price', 'subtotal']
        read_only_fields = ['id', 'price', 'subtotal']

    def get_subtotal(self, obj):
        return obj.subtotal()

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate(self, attrs):
        order = attrs.get('order')
        if order and order.status != Order.Status.PENDING:
            raise serializers.ValidationError("Items can only be added to pending orders.")
        return attrs

    def create(self, validated_data):
        validated_data['price'] = validated_data['vendor_product'].price
        return super().create(validated_data)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'method', 'transaction_id', 'status', 'created_at']
        read_only_fields = ['id', 'amount', 'transaction_id', 'status', 'created_at']

    def validate_order(self, value):
        user = self.context['request'].user
        # Ensure order belongs to the user
        if not user.is_staff and value.user != user:
            raise serializers.ValidationError("You can only create a payment for your own order.")
        # Ensure order is pending
        if value.status != Order.Status.PENDING:
            raise serializers.ValidationError("Payment can only be created for a pending order.")
        # Ensure order doesn't already have a payment
        if self.instance is None and Payment.objects.filter(order=value).exists():
            raise serializers.ValidationError("This order already has a payment.")
        return value

    def validate_method(self, value):
        if value != Payment.Mode.COINS:
            raise serializers.ValidationError("Only COINS payment method is supported currently.")
        return value

    def validate(self, attrs):
        order = attrs.get('order')
        user = self.context['request'].user
        # Validate coins for COINS method
        if attrs.get('method') == Payment.Mode.COINS:
            if user.coins < order.total_price:
                raise serializers.ValidationError("Insufficient coins for this payment.")
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            order = validated_data['order']
            user = self.context['request'].user
            validated_data['amount'] = order.total_price
            # Deduct coins for COINS method
            if validated_data['method'] == Payment.Mode.COINS:
                user.coins -= order.total_price
                user.save()
                validated_data['status'] = Payment.Status.COMPLETED
                order.status = Order.Status.PAID
                order.save()
            payment = Payment.objects.create(**validated_data)
            return payment


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, allow_empty=False)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'payment','status', 'order_items', 'created_at', 'total_price']
        read_only_fields = ['id', 'created_at', 'total_price', 'user']

    def create(self, validated_data):
        items_data = validated_data.pop('order_items')
        user = self.context['request'].user
        order = Order.objects.create(user=user, **validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('order_items', None)
        instance = super().update(instance, validated_data)

        if items_data:
            instance.order_items.all().delete()
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)

        return instance



class ShippingAddressSerializer(serializers.ModelSerializer):
    phone = PhoneNumberField()
    country = CountryField()

    class Meta:
        model = ShippingAddress
        fields = ['id', 'order', 'receiver', 'address_line', 'city', 'postal_address', 'country', 'phone']
        read_only_fields = ['id']

    def validate_order(self, value):
        user = self.context['request'].user
        # Ensure order belongs to the user
        if not user.is_staff and value.user != user:
            raise serializers.ValidationError("You can only add a shipping address to your own order.")
        # Ensure order is pending
        if value.status != Order.Status.PENDING:
            raise serializers.ValidationError("Shipping address can only be added to a pending order.")
        # Ensure order doesn't already have a shipping address
        if self.instance is None and ShippingAddress.objects.filter(order=value).exists():
            raise serializers.ValidationError("This order already has a shipping address.")
        return value

    def validate(self, attrs):
        # Ensure required text fields are not empty
        for field in ['receiver', 'address_line', 'city', 'postal_address']:
            if not attrs.get(field, '').strip():
                raise serializers.ValidationError({field: f"{field.replace('_', ' ').title()} cannot be empty."})
        return attrs



