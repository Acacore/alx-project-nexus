from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from .serializers import *
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate, login
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from .models import Order, Payment, OrderItem, VendorProduct, Vendor
from .serializers import OrderSerializer


# Create your views here.
def home(request):
    return HttpResponse("<h1>Hello, World <br> Wellcome to Mercarol</h1>")

class APIRootView(APIView):
    permission_classes = [AllowAny]  # public

    def get(self, request):
        return Response({"message": "Welcome to the API"})
    


class LoginAPIView(APIView):
    permission_classes = [AllowAny]  # Anyone can access login

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({"error": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)  # creates session if using SessionAuthentication
            return Response({
                "message": "Login successful",
                "email": user.email,
                "username": user.username,
                "role": user.role
            })

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class UserViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing accounts.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return User.objects.all()
        else:
            return User.objects.filter(pk=user.pk)
        
    def perform_destroy(self, instance):
        user = self.request.user

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("You do not have permission to delete your account")
        instance.delete()


class ViendorViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Vendor.
    """
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Vendor.objects.all()
        else:
            return Vendor.objects.filter(user=user)

class CategoryViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Vendor.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()

    def perform_create(self, serialiser):
        user = self.request.user

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("You do not have permission to create a new Catagory")
        serialiser.save()

    
    def perform_upate(self, serialiser):
        user = self.request.user

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("You do not have permission to update a Catagory")
        serialiser.save()

    def perform_destroy(self, instance):
        user = self.request.user

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("You do not have permission to delete a category")
        instance.delete()

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()

    def perform_create(self, serializer):
        #Prevent users from creating Products
        user = self.request.user
        print(user.role)
        if user.role != 'VENDOR':
            raise PermissionDenied("You do not have permission to craete a Product")
        serializer.save(vendor=user)

    def update(self, request, *args, **kwargs):
        #Prevent users from creating Products
        raise PermissionDenied("You do not have permission to craete a Product")

    def partial_update(self, request, *args, **kwargs):
        #Prevent users from creating Products
        raise PermissionDenied("You do not have permission to craete a Product")
    
    
    def destroy(self, request, *args, **kwargs):
        user = self.request.user

        if not (user.is_staff or user.is_superuser):
            raise PermissionDenied("You do not have permission to delete a category")
        return super().destroy(request, *args, **kwargs)


    

class VendorProductViewset(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Vendor.
    """
    serializer_class = VendorProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = VendorProduct.objects.all()


    def get_queryset(self):
        user = self.request.user
        queryset = VendorProduct.objects.all()

        product_name = self.request.query_params.get('vendor')
        print(product_name)
        product_id = self.request.query_params.get('id')
        
        if product_name:
            queryset = queryset.filter(product=product_name)
        
        if product_id:
            queryset = queryset.filter(id=product_id)
 
        # Admin can only see all variant
        if user.is_staff or user.is_superuser:
            return ProductVariant.objects.all()
        
        elif user.role == 'VENDOR':
            return ProductVariant.objects.filter(vendor_product__vendor__user=user)
        else:
            return queryset
    

    def perform_create(self, serializer):
        user = self.request.user
        print(user.role)
        if user.role != User.Roles.VENDOR:
            raise PermissionDenied("You do not have permission to create a new Product Details")
    
        try:
            vendor_instance = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("No Vendor profile found for this user")
        
        serializer.save(vendor=vendor_instance)

    


    def perform_destroy(self, instance):
        user = self.request.user

        if not (user.role!= 'VENDOR'):
            raise PermissionDenied("You do not have permission to delete a category")
        instance.delete()



class ProductVariantViewset(viewsets.ModelViewSet):
   
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]
    

    def get_queryset(self):
        user = self.request.user
        queryset = ProductVariant.objects.all()

        product_name = self.request.query_params.get('name')
        product_id = self.request.query_params.get('id')
        
        if product_name:
            queryset = queryset.filter(vendor_product__product__name__icontains=product_name)
        
        if product_id:
            queryset = queryset.filter(vendor_product__id=product_id)

        # Admin can only see all variant
        if user.is_staff or user.is_superuser:
            return ProductVariant.objects.all()
        
        elif user.role == 'VENDOR':
            return ProductVariant.objects.filter(vendor_product__vendor__user=user)
        else:
            return queryset
        
    def perform_create(self, serializer):
        user = self.request.user

        # Only vendors can create variants
        if user.role != User.Roles.VENDOR:
            raise PermissionDenied("You do not have permission to create a new ProductVariant")

        # Get the vendor instance
        try:
            vendor_instance = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("No Vendor profile found for this user")

        # Get the vendor_product instance from POST data
        vendor_product_id = self.request.data.get('vendor_product')
        try:
            vendor_product = VendorProduct.objects.get(id=vendor_product_id, vendor=vendor_instance)
        except VendorProduct.DoesNotExist:
            raise PermissionDenied("Invalid vendor_product or not owned by you")

        # Save the variant
        serializer.save(vendor_product=vendor_product)
    
    def perform_destroy(self, instance):
        user = self.request.user

        if not (user.role!= 'VENDOR'):
            raise PermissionDenied("You do not have permission to delete a category")
        instance.delete()

class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# class OrderViewSet(viewsets.ModelViewSet):
#     serializer_class = OrderSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         user = self.request.user
#         queryset = Order.objects.all()
#         if user.is_staff or user.is_superuser:
#             return queryset
#         return queryset.filter(user=user)

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['request'] = self.request
#         return context

#     def perform_destroy(self, instance):
#         user = self.request.user
#         if instance.user != user and not (user.is_staff or user.is_superuser):
#             raise PermissionDenied("You do not have permission to delete this order")
#         if instance.status != Order.Status.PENDING:
#             raise PermissionDenied("You cannot delete an order that has already been processed")
#         instance.delete()

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(user=user)

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_destroy(self, instance):
        if instance.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot delete a processed order.")
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def mark_as_shipped(self, request, pk=None):
        """
        Allows a vendor to mark an order as SHIPPED if they own products in the order
        and the payment is COMPLETED.
        """
        order = self.get_object()
        user = request.user

        # Check if user is a vendor
        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("You are not a vendor.")

        # Check if order has a completed payment
        if not hasattr(order, 'payment') or order.payment.status != Payment.Status.COMPLETED:
            raise PermissionDenied("Order does not have a completed payment.")

        # Check if vendor's products are in the order
        vendor_products = VendorProduct.objects.filter(vendor=vendor).values_list('id', flat=True)
        if not OrderItem.objects.filter(order=order, vendor_product__id__in=vendor_products).exists():
            raise PermissionDenied("You are not associated with any products in this order.")

        # Check if order is in PAID status
        if order.status != Order.Status.PAID:
            raise PermissionDenied("Order must be in PAID status to mark as shipped.")

        # Update order status to SHIPPED
        order.status = Order.Status.SHIPPED
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = OrderItem.objects.all()
        # Filter by vendor_product_id if provided
        vendor_product_id = self.request.query_params.get('vendor_product_id')
        if vendor_product_id:
            queryset = queryset.filter(vendor_product_id=vendor_product_id)
        # Admin can see all items
        if user.is_staff or user.is_superuser:
            return queryset
        # Role-based filtering
        if hasattr(user, 'role'):
            if user.role == 'CUSTOMER':
                return queryset.filter(order__user=user)
            elif user.role == 'VENDOR':
                return queryset.filter(vendor_product__vendor__user=user)
        return queryset.none()  # Empty queryset for users without a role

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save()  # Validation handled by OrderItemSerializer

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.order.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot delete an order item from a processed order.")
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied("You do not have permission to delete this order item.")
        instance.delete()




class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ShippingAddress.objects.all()
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        # Validation is handled by the serializer, so just save
        serializer.save()

    def perform_update(self, serializer):
        # Ensure the user can only update their own shipping address
        user = self.request.user
        instance = self.get_object()
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied("You do not have permission to update this shipping address.")
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied("Cannot update a shipping address for a processed order.")
        serializer.save()

    def perform_destroy(self, instance):
        # Ensure the user can only delete their own shipping address
        user = self.request.user
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied("You do not have permission to delete this shipping address.")
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied("Cannot delete a shipping address for a processed order.")
        instance.delete()


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ShippingAddress.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied("Cannot update a shipping address for a processed order.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied("Cannot delete a shipping address for a processed order.")
        instance.delete()



class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status != Payment.Status.PENDING:
            raise PermissionDenied("Cannot update a completed or failed payment.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Payment.Status.PENDING:
            raise PermissionDenied("Cannot delete a completed or failed payment.")
        instance.delete()