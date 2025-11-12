from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from .serializers import *
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate, login
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied


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



class OrderViewset(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        user=self.request.user
        queryset = Order.objects.all()

        # Admin can only see all variant
        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        user = self.request.user

        if instance.user != user:
            raise PermissionDenied("You do not have permission to delete a category")
        

        if instance.status != 'pending':
            raise PermissionDenied("You can not delete an order that has already been process")
        
        instance.delete()



class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes=[IsAuthenticated]
    

    def get_queryset(self):
        user=self.request.user
        queryset=OrderItem.objects.all()

        # Filter by query param if provided
        product_id = self.request.query_params.get('id')
        if product_id:
            queryset = queryset.filter(id=product_id)

        # Admin can only see all variant
        if user.is_staff or user.is_superuser:
            return queryset
        
        if hasattr(user, 'role') and user.role == 'CUSTOMER':
            return queryset.filter(order__user=user)
        
        if hasattr(user, 'role') and user.role == 'VENDOR':
            return queryset.filter(product__vendor__user=user)
        
        return queryset
       

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(user=user)
    
    def perform_destroy(self, instance):
        user = self.request.user
        instance.delete()


        if instance.order.status != 'pending':
            raise PermissionDenied("Cannot delete and order item from a processed order")
        
        if not (user.is_staff or user.is_superuser) and instance.order.user != user:
            raise PermissionDenied("You do not have permission to delete this order item")
        
        instance.delete()