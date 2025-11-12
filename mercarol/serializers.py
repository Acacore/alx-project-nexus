from rest_framework import serializers
from .models import *


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
        fields = '__all__'

    def get_subtotal(self, obj):
        return obj.quantity * obj.ventor_product.price
    

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")

        return value
    
    def validate(self, attrs):
        vendor_product = attrs.get('vendor_product')
        order = attrs.get('order')

        if vendor_product is None:
            raise serializers.ValidationError("Vendor product is required")

        if order.status != 'PENDING':
             raise serializers.ValidationError("You cannot add items to a non-pending order.")
        return attrs

    
    
class OrderSerializer(serializers.ModelSerializer):
    items =  OrderItemSerializer(many=True, allow_empty=False)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'total_price', 'user']


    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required')
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.craete(order=order, **item_data)
        return order    


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'


class PayementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payement
        fields = '__all__'
        read_only_fields = ['id', 'transaction', 'customer', 'status']


    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidtionError('Amount must be greater than zero')