from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from .serializers import *
from .permissions import *
from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny, IsAuthenticatedOrReadOnly
from django.db import IntegrityError, transaction
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate, login
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from django.db.models import Q, Prefetch
from .permissions import WatchlistPermission, CommentPermission
from .tasks import *
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema
import logging
from .filter import *
from rest_framework import filters
from django.urls import reverse_lazy
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from djoser.serializers import UserCreateSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from rest_framework.parsers import MultiPartParser, FormParser
from mercarol.tasks import send_category_created_email

User = get_user_model()
logger = logging.getLogger('mercarol')


class LoginOrSignupView(generics.GenericAPIView):
    """
    Allows users to log in or automatically sign up:
    
    - If email exists → authenticate and return tokens.
    - If email does not exist → create account and return tokens.
    """
    serializer_class = UserCreateSerializer

    def post(self, request):
        email = request.data.get("email")
        username = request.data.get("username")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "Email and password required"}, status=400)

        try:
            user = User.objects.get(email=email)
            if check_password(password, user.password):
                refresh = RefreshToken.for_user(user)
                return Response({
                    "status": "logged_in",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token)
                })
            else:
                return Response({"error": "Incorrect password"}, status=400)
        except User.DoesNotExist:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "status": "signed_up",
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }, status=201)



def default_redirect(request):
    
    return redirect('/api/schema/swagger-ui/')
    

class LargeResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class APIRootView(APIView):
    permission_classes = [AllowAny]  # public

    def get(self, request):
        return Response({"message": "Welcome to the API"})


class LoginAPIView(APIView):
    permission_classes = [AllowAny]  # Anyone can access login

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)  # creates session if using SessionAuthentication
            return Response(
                {
                    "message": "Login successful",
                    "email": user.email,
                    "username": user.username,
                    "role": user.role,
                }
            )

        return Response(
            {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    Handles user accounts with restricted access:
    - Admins: can view, update, and delete any user.
    - Regular users: can only view, update, or delete their own account.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return User.objects.all()
        return User.objects.filter(pk=user.pk)

    def perform_update(self, serializer):
        user = self.request.user
        if serializer.instance != user and not (user.is_staff or user.is_superuser):
            raise PermissionDenied("You can only update your own account.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance != user and not (user.is_staff or user.is_superuser):
            raise PermissionDenied("You can only delete your own account.")
        instance.delete()




class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()

    def _require_staff(self, action: str):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied(
                f"You do not have permission to {action} a category."
            )

    def perform_create(self, serializer):
        self._require_staff("create")
        category = serializer.save()
        return category   # <-- important!

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # save and get the created object
        category = self.perform_create(serializer)

        try:
            send_category_created_email.delay(
            category_name=category.name,
            created_by_email=self.request.user.email
            )
        except Exception as e:
            # Log the error, but don’t break the API response
            logger.error(f"Failed to send category email: {e}")


        return Response(
            {"message": f"Category '{category.name}' created successfully."},
            status=status.HTTP_201_CREATED
        )


    # UPDATE
    def update(self, request, *args, **kwargs):
        self._require_staff("update")
        partial = kwargs.pop("partial", False)  # for PATCH support
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {"message": f"Category '{serializer.data['name']}' updated successfully"},
            status=status.HTTP_200_OK  
        )

    def destroy(self, request, *args, **kwargs):
        self._require_staff("delete")
        instance = self.get_object()
        self.perform_destroy(instance)

        return Response(
            {"message": f"Category '{instance.name}' has been deleted."},
            status=status.HTTP_200_OK
        )


class VendorViewSet(viewsets.ModelViewSet):
    """
    Vendor can manage only their own vendor profile;
    staff/superusers have full access.
    """

    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Vendor.objects.all()
        return Vendor.objects.filter(user=user)

    def _check_owner_or_admin(self, obj, action="update"):
        if obj.user != self.request.user and not (
            self.request.user.is_staff or self.request.user.is_superuser
        ):
            raise PermissionDenied(f"You can only {action} your own vendor profile.")


    def perform_create(self, serializer):
        if Vendor.objects.filter(user=self.request.user).exists():
            raise PermissionDenied("You already have a vendor profile.")
        serializer.save(user=self.request.user)


    
    def perform_update(self, serializer):
        self._check_owner_or_admin(serializer.instance, "update")
        serializer.save()

   
    def perform_destroy(self, instance):
        self._check_owner_or_admin(instance, "delete")
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    """
    Manages products with role-based access:

    - Admins: full access to all products.
    - Vendors: can create and manage their own products.
    - Customers/anonymous users: blocked and redirected to vendor product listings.
    Supports image/file uploads through multipart parsing.
    """
      
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Product.objects.all()
    parser_classes = [MultiPartParser, FormParser]
  
  

    def get_queryset(self):
      
        user = self.request.user

        # Admin → all products
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return Product.objects.all()

        # Vendor → products created by vendor + admin products
        if user.is_authenticated and user.role == User.Roles.VENDOR:
             return Product.objects.filter(Q(user=user) | Q(user__is_staff=True) | Q(user__is_superuser=True))
        # Customers / visitors → empty queryset (redirect handled in list())
        return Product.objects.none()

    def list(self, request, *args, **kwargs):
        user = request.user

        # Anonymous users → 401 Unauthorized
        if not user.is_authenticated:
            return Response(
                {
                    "detail": "Authentication required to view products. Please view vendor offerings.",
                    "redirect_to": "/api/vendor-product/"
                },
                status=401
            )

        # Customers → 403 Forbidden
        if getattr(user, "role", None) == User.Roles.CUSTOMER:
            return Response(
                {
                    "detail": "Direct product listing is restricted for customers. Please view vendor offerings.",
                    "redirect_to": "/api/vendor-product/"
                },
                status=403
            )

        # Admin or Vendor → normal product list
        # This will automatically use get_queryset()
        return super().list(request, *args, **kwargs)

    # ------ CREATE ------
    def perform_create(self, serializer):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        # Admin can create products without vendor
        if user.is_staff or user.is_superuser:
            serializer.save(user=user)

        # Vendor can create products with themselves as vendor
        elif user.role == User.Roles.VENDOR:
            serializer.save(user=user)
        else:
            raise PermissionDenied("Only vendors or admins can create products.")


    # ------ UPDATE ------
    def perform_update(self, serializer):
        user = self.request.user

        # Admin → update anything
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            serializer.save()
            return

        # Vendor → only their own products
        if user.is_authenticated and user.role == User.Roles.VENDOR:
            if serializer.instance.vendor != user:
                raise PermissionDenied("You can only modify your own products.")
            serializer.save()
            return
        
        # All others → deny
        raise PermissionDenied("You do not have permission to update this product.")


    def perform_destroy(self, instance):
        user = self.request.user

        # Admin → can delete any product
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            instance.delete()
            return

        # Vendor → can delete their own products
        if user.is_authenticated and user.role == User.Roles.VENDOR:
            if instance.vendor != user:
                raise PermissionDenied("You can only delete your own products.")
            instance.delete()
            return

        # All others → deny
        raise PermissionDenied("You do not have permission to delete this product.")


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    Vendors manage their own product variants.
    Staff/superusers have full access.
    """

    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]
    queryset = ProductVariant.objects.all()
    

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Optional filters
        product_name = self.request.query_params.get("name")
        product_id = self.request.query_params.get("id")

        if product_name:
            queryset = queryset.filter(
                vendor_product__product__name__icontains=product_name
            )
        if product_id:
            try:
                queryset = queryset.filter(vendor_product__id=int(product_id))
            except (ValueError, TypeError):
                pass

        if user.is_staff or user.is_superuser:
            return queryset

        if getattr(user, "role", None) == User.Roles.VENDOR:
            return queryset.filter(vendor_product__vendor__user=user)

        # Allow public filtering (e.g. name, id) — safer than .none()
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can create variants.")

        vendor = get_object_or_404(Vendor, user=user)
        vendor_product = serializer.validated_data["vendor_product"]

        if vendor_product.vendor != vendor:
            raise PermissionDenied("You can only add variants to your own products.")

        # Check for duplicate name
        if ProductVariant.objects.filter(
            vendor_product=vendor_product,
            name__iexact=serializer.validated_data["name"],
        ).exists():
            raise serializers.ValidationError(
                "You already created a variant with this name for this product."
            )

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            serializer.save()
            return

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can update variants.")

        instance = serializer.instance
        if instance.vendor_product.vendor.user != user:
            raise PermissionDenied("You can only update your own variants.")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            instance.delete()
            return

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can delete variants.")

        if instance.vendor_product.vendor.user != user:
            raise PermissionDenied("You can only delete your own variants.")

        instance.delete()

class VendorProductViewSet(viewsets.ModelViewSet):
    """
    Vendors can manage their own VendorProduct items.
    Staff and superusers have full access.
    """
    serializer_class = VendorProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = VendorProduct.objects.filter(is_available=True).select_related('vendor', 'vendor__user')

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset

        # Optional filters
        vendor_name = self.request.query_params.get("vendor")
        product_id = self.request.query_params.get("id")

        if vendor_name:
            queryset = queryset.filter(vendor__name__icontains=vendor_name)

        if product_id:
            queryset = queryset.filter(id=product_id)

        # Admins see everything
        if user.is_staff or user.is_superuser:
            return queryset

        # Vendors see:
        # - their own vendor products
        # - vendor products linked to admin-created products
        if getattr(user, "role", None) == User.Roles.VENDOR:
            return queryset.filter(
                Q(vendor__user=user) | Q(product__user__is_staff=True) | Q(product__user__is_superuser=True)
            )

        # Others browse through the product to purchase them.
        return VendorProduct.objects.all()

    def perform_create(self, serializer):
        user = self.request.user

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can create vendor products.")

        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("You don’t have a vendor profile yet.")

        serializer.save(vendor=vendor)

    def perform_update(self, serializer):
        user = self.request.user

        # Admins can update anything
        if user.is_staff or user.is_superuser:
            serializer.save()
            return

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can update vendor products.")

        instance_vendor_user = getattr(getattr(serializer.instance, 'vendor', None), 'user', None)
        if instance_vendor_user != user:
            raise PermissionDenied("You can only update your own vendor products.")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user

        # Admins can delete anything
        if user.is_staff or user.is_superuser:
            instance.delete()
            return

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can delete their own vendor products.")

        instance_vendor_user = getattr(getattr(instance, 'vendor', None), 'user', None)
        if instance_vendor_user != user:
            raise PermissionDenied("You can only delete your own vendor products.")

        instance.delete()



class CartViewSet(viewsets.ModelViewSet):
    """
    Manages the authenticated user's shopping cart.

    Each user has one cart. Items can be added or updated via POST,
    and users can only view or modify their own cart.
    """

    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    queryset = Cart.objects.all()

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user

        # Block manual user override
        if "user" in self.request.data:
            raise ValidationError({"user": "You cannot set the user field."})

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own cart.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own cart.")
        instance.delete()


class CartItemViewSet(viewsets.ModelViewSet):
    """
    Manages items in the user's shopping cart.

    Automatically assigns items to the authenticated user's cart and
    only returns cart items belonging to that user.
    """
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        serializer.save(cart=cart)



class OrderViewSet(viewsets.ModelViewSet):
    """
    Manages customer orders and vendor visibility.

    Customers can access their own orders, vendors can view orders
    containing their products, and staff can view all. Orders cannot be
    created directly and can only be modified while pending. Vendors
    may mark their items in an order as shipped once payment is completed.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_staff or user.is_superuser:
            return queryset

        # Regular users: only their own orders
        if not hasattr(user, "role") or user.role != User.Roles.VENDOR:
            return queryset.filter(user=user)

        # Vendors: orders containing their products
        try:
            vendor = user.vendor
        except AttributeError:
            return queryset.none()

        vendor_product_ids = VendorProduct.objects.filter(vendor=vendor).values_list(
            "id", flat=True
        )
        return queryset.filter(
            items__vendor_product__id__in=vendor_product_ids
        ).distinct()

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        # Only allow creation via checkout (not direct API)
        raise PermissionDenied("Orders cannot be created directly. Use checkout.")

    def perform_update(self, serializer):
        # Prevent status tampering
        if "status" in self.request.data:
            raise PermissionDenied("You cannot modify the order status.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot delete a processed order.")
        if instance.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only delete your own pending orders.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def mark_as_shipped(self, request, pk=None):
        """
        Vendor can mark THEIR items in the order as SHIPPED.
        Order must be PAID and have completed payment.
        """
        order = self.get_object()
        user = request.user

        # 1. Must be vendor
        try:
            vendor = user.vendor
        except AttributeError:
            raise PermissionDenied("You are not a vendor.")

        # 2. Order must have completed payment
        try:
            if order.payment.status != Payment.Status.COMPLETED:
                raise PermissionDenied("Payment is not completed.")
        except AttributeError:
            raise PermissionDenied("Order has no payment record.")

        # 3. Order must be PAID
        if order.status != Order.Status.PAID:
            raise PermissionDenied("Order must be in PAID status.")

        # 4. Vendor must have items in this order
        vendor_items = order.items.filter(vendor_product__vendor=vendor)
        if not vendor_items.exists():
            raise PermissionDenied("You have no items in this order.")

        # 5. Mark only vendor's items as shipped
        updated = vendor_items.update(shipment_status=OrderItem.ShipmentStatus.SHIPPED)
        if updated:
            # Optional: trigger notification, update order if all shipped
            order.refresh_from_db()
            if order.items.filter(
                shipment_status=OrderItem.ShipmentStatus.PENDING
            ).exists():
                pass  # still partial
            else:
                order.status = Order.Status.SHIPPED
                order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    Manages items within an order.

    Customers can access items in their own orders, vendors can view items
    related to their products, and staff can view all. Items can only be
    created, updated, or deleted while the order is still pending.
    """
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]
    queryset = OrderItem.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Optional filter
        vendor_product_id = self.request.query_params.get("vendor_product_id")
        if vendor_product_id:
            try:
                queryset = queryset.filter(vendor_product_id=int(vendor_product_id))
            except (ValueError, TypeError):
                pass  # ignore invalid ID

        # Admins see all
        if user.is_staff or user.is_superuser:
            return queryset

        role = getattr(user, "role", None)

        if role == "CUSTOMER":
            return queryset.filter(order__user=user)
        elif role == "VENDOR":
            return queryset.filter(vendor_product__vendor__user=user)

        return queryset.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        user = self.request.user
        role = getattr(user, "role", None)

        # Extract order from data
        order_id = self.request.data.get("order")
        if not order_id:
            raise ValidationError({"order": "This field is required."})

        try:
            order = Order.objects.get(id=order_id)
            

        except Order.DoesNotExist:
            raise ValidationError({"order": "Invalid order."})

        # Only allow adding to PENDING orders
        if order.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot add items to a processed order.")

        # Only owner (customer) or staff can modify
        if not (user.is_staff or user.is_superuser or order.user == user):
            raise PermissionDenied("You can only add items to your own pending order.")

        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.order.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot modify items in a processed order.")
        if not (self.request.user.is_staff or instance.order.user == self.request.user):
            raise PermissionDenied(
                "You can only update items in your own pending order."
            )
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.order.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot delete items from a processed order.")
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied(
                "You can only delete items from your own pending order."
            )
        instance.delete()

class ShippingAddressViewSet(viewsets.ModelViewSet):
    """
    Handles creating and managing shipping addresses.

    Users can manage their own addresses, while staff can view all.
    New addresses are automatically linked to the authenticated user.
    """
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return ShippingAddress.objects.all()
        return ShippingAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    Manages user payment records.

    Users can view their own payments, while staff can view all.
    Payments cannot be updated, and deletion is only allowed for
    pending payments owned by the user. Vendors can confirm
    disbursement for completed payments linked to their products.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()

  
    # Role-based list
  
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(order__user=user)

  
    # Pass request to serializer
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

  
    # Updates – **blocked** (payments are immutable after creation)
   
    def perform_update(self, serializer):
        raise PermissionDenied("Payments cannot be updated after creation.")



  
    def perform_destroy(self, instance):
        if instance.status != Payment.Status.PENDING:
            raise PermissionDenied(
                "Cannot delete a completed or failed payment."
            )
        if instance.order.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied(
                "You can only delete your own pending payment."
            )
        instance.delete()

  
    # Vendor confirms disbursement
   
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="confirm-vendor-payment",
    )
    def confirm_vendor_payment(self, request, pk=None):
        payment = self.get_object()
        user = request.user

        # Must be a vendor
        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("You are not a vendor.")

        # Vendor must have items in the order
        vp_ids = VendorProduct.objects.filter(vendor=vendor).values_list("id", flat=True)
        if not OrderItem.objects.filter(
            order=payment.order, vendor_product__id__in=vp_ids
        ).exists():
            raise PermissionDenied("You are not associated with this order.")

        # Payment must be COMPLETED
        if payment.status != Payment.Status.COMPLETED:
            raise PermissionDenied("Payment must be completed before disbursement.")

        # Atomic update
        with transaction.atomic():
            # Re-fetch with lock to avoid race
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            if payment.vendor_payment_status == Payment.VendorStatus.DISBURSED:
                raise PermissionDenied("Vendor payment already disbursed.")
            payment.vendor_payment_status = Payment.VendorStatus.DISBURSED
            payment.save(update_fields=["vendor_payment_status"])

        return Response(self.get_serializer(payment).data)


@extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
class CheckoutViewSet(viewsets.ViewSet):
    """
    Handles the checkout process for the authenticated user.

    Validates the cart, checks stock and wallet balance, creates the order
    and payment record, updates product stock, deducts user coins, and clears the cart.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CheckoutSerializer 
        
    @extend_schema(
        responses={201: OrderSerializer},
    )

    @transaction.atomic
    def create(self, request):
        user = request.user

        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Lock the user row
        user = User.objects.select_for_update().get(pk=user.pk)

        # Get cart items
        cart_items = (
            CartItem.objects
            .filter(cart__user=user)
            .select_related("vendor_product")
        )

        if not cart_items.exists():
            raise ValidationError("Your cart is empty.")

        # Lock all products (MUST evaluate queryset!)
        product_ids = [item.vendor_product_id for item in cart_items]
        list(
            Product.objects
            .select_for_update()
            .filter(id__in=product_ids)
        )

        # Check stock & compute totals
        total_price = 0
        order_items = []

        for item in cart_items:
            product = item.vendor_product

            if item.quantity > product.stock:
                raise ValidationError(f"Not enough stock for {product.name}")

            total_price += item.subtotal()

            order_items.append(
                OrderItem(
                    order=None,
                    vendor_product=product,
                    quantity=item.quantity,
                    price=product.price,
                )
            )

        # Check user coins
        if user.coins < total_price:
            needed = total_price - user.coins
            raise ValidationError({
                "detail": (
                    f"Insufficient coins. You need {needed} more coins. "
                    f"Balance: {user.coins}, Required: {total_price}"
                )
            })

        # Create order
        order = Order.objects.create(
            user=user,
            shipping=serializer.validated_data["shipping_address"],
            total_price=total_price,
        )

        # Attach order to items
        for oi in order_items:
            oi.order = order

        OrderItem.objects.bulk_create(order_items)

        # Deduct wallet
        user.coins -= total_price
        user.save()

        # Deduct product stock
        for item in cart_items:
            product = item.vendor_product
            product.stock -= item.quantity
            product.save()

        # Create payment record
        Payment.objects.create(
            order=order,
            amount=total_price,
            method=serializer.validated_data["payment_method"],
            status=Payment.Status.COMPLETED,
        )

        # Clear cart
        cart_items.delete()

        return Response({
            "message": "Checkout completed successfully!",
            "order_id": order.id,
        }, status=201)



class AuctionItemViewSet(viewsets.ModelViewSet):
    """
    Auction Item ViewSet.

    Roles:
    - Public: list & retrieve active auctions
    - Vendors: create, update, cancel their own auctions
    - Staff/Admin: full access
    """

    qs = AuctionItem.objects.all().select_related(
        "vendor_product", "vendor_product__vendor", "vendor_product__vendor__user"
    )
    
    serializer_class = AuctionItemSerializer
    permission_classes = [IsAuthenticated]
    

    def get_queryset(self):
        user = self.request.user
        qs = AuctionItem.objects.select_related('product', 'winner').prefetch_related('bids__user', 'watchers', 'comments')

        # PUBLIC + CUSTOMER (unauthenticated or authenticated but NOT vendor/admin)
        if not user.is_authenticated or not (user.is_staff or getattr(user, 'role', None) == 'VENDOR'):
            return qs.filter(status=AuctionItem.Status.ACTIVE, end_time__gt=timezone.now())

        # VENDOR
        if getattr(user, 'role', None) == 'VENDOR':
            return qs.filter(product__vendor__user=user)

        # ADMIN
        return qs

    # Create auction: only vendors or staff, only for own product
    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data['product']  # VendorProduct instance

        # Only vendors can create auctions
        if not (hasattr(user, 'role') and user.role == "VENDOR"):
            raise PermissionDenied("Only vendors can create auctions.")

        # Vendor must own the product
        if product.vendor.user != user:
            raise PermissionDenied("You can only auction your own products.")

        # Prevent auction if product is not in stock
        if product.stock <= 0:
            raise PermissionDenied("This product is not in stock and cannot be auctioned.")
        
        # Create the auction
        auction = serializer.save(
        vendor=user,
        current_bid=serializer.validated_data['start_price'],
        status=AuctionItem.Status.ACTIVE
    )
        
        
        product.is_available=False
        product.save()

        # Soft delete the product from VendorProduct list (delete from inventory)
        

        return auction


    # Update auction: only before start, only owner or staff
    def perform_update(self, serializer):
        auction = self.get_object()
        user = self.request.user

        if not (user.is_staff or auction.product.vendor.user == user):
            raise PermissionDenied("You can only update your own auctions.")

        if auction.has_started():
            raise PermissionDenied("Cannot update an auction that has started.")

        serializer.save()

    # Delete auction: soft-cancel
    def perform_destroy(self, instance):
        user = self.request.user
        if not (user.is_staff or instance.product.vendor.user == user):
            raise PermissionDenied("You can only cancel your own auctions.")

        if instance.status != AuctionItem.Status.ACTIVE:
            raise PermissionDenied("Cannot cancel an ended or already cancelled auction.")

        instance.status = AuctionItem.Status.CANCELLED
        instance.save(update_fields=['status'])

    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, IsCustomer],
        serializer_class=BidSerializer
    )
    def place_bid(self, request, pk=None):
        auction = self.get_object()
        
        # Minimum required increment for bids
        MIN_INCREMENT = Decimal("1.00")

        # Initial validation
        data = request.data.copy()
        data['auction_id'] = str(auction.id)
        serializer = self.get_serializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        max_bid = serializer.validated_data.get('max_bid', amount)
        user = request.user

        # Concurrency-safe processing
        try:
            with transaction.atomic():
                # Lock the auction row to prevent race conditions
                auction = AuctionItem.objects.select_for_update().get(pk=auction.pk)

                # Check if auction is still open
                if auction.status != AuctionItem.Status.ACTIVE or auction.end_time < timezone.now():
                    return Response(
                        {"detail": "Auction is no longer open for bidding."},
                        status=status.HTTP_400_BAD_REQUEST
                    )


                highest = auction.bids.order_by('-amount').first()
                current_high = highest.amount if highest else auction.start_price

                # Enforce minimum increment
                min_required_bid = current_high + MIN_INCREMENT
                if amount < min_required_bid:
                    raise ValidationError({
                        'amount': f"Bid must be at least {MIN_INCREMENT} higher than the current bid of {current_high}. Minimum required: {min_required_bid}"
                    })

                # Proxy bidding logic
                new_bid_amount = amount
                if highest and highest.user != user:
                    opponent_max = highest.max_bid
                    if max_bid > opponent_max:
                        # Beat the opponent just enough
                        new_bid_amount = min(max_bid, opponent_max + MIN_INCREMENT)
                    elif max_bid == opponent_max:
                        # Tie: first bidder remains highest
                        new_bid_amount = opponent_max

                # Create or update bid record
                bid, _ = Bid.objects.update_or_create(
                    auction=auction,
                    user=user,
                    defaults={'amount': new_bid_amount, 'max_bid': max_bid}
                )

                # Update current bid safely
                auction.current_bid = max(auction.current_bid, new_bid_amount)
                auction.save(update_fields=['current_bid'])

                # Send notification asynchronously
                send_bid_notification.delay(bid.id)

        # Error handling
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except AuctionItem.DoesNotExist:
            return Response({"detail": "Auction item not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error placing bid on auction {pk}: {e}")
            return Response(
                {"detail": "An internal error occurred during bidding. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Success response
        return Response({
            "detail": "Bid placed successfully.",
            "current_bid": auction.current_bid,
            "your_bid": new_bid_amount,
            "max_bid_set": max_bid
        }, status=status.HTTP_201_CREATED)



    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], serializer_class=WinnerSerialiazer)
    def declare_winner(self, request, pk=None):
            auction = self.get_object()
            user = request.user

            # Permission: vendor or staff only
            if not (user.is_staff or auction.product.vendor.user == user):
                raise PermissionDenied("You can only declare a winner for your own auctions.")

            # Auction must be ended
            if auction.is_active():
                raise ValidationError("Cannot declare a winner before the auction ends.")

            # Determine highest bid
            highest_bid = auction.bids.order_by('-amount').first()
            if not highest_bid:
                return Response({"detail": "No bids placed. Cannot declare a winner."}, status=status.HTTP_400_BAD_REQUEST)

            # Set winner
            auction.winner = highest_bid.user
            auction.status = AuctionItem.Status.ENDED
            auction.save(update_fields=['winner', 'status'])

            return Response({
                "detail": f"The winner is {highest_bid.user.username}",
                "winning_bid": highest_bid.amount
            }, status=status.HTTP_200_OK)


class AuctionItemViewSet(viewsets.ModelViewSet):
    """
    Auction Item ViewSet.

    Roles:
    - Public: list & retrieve active auctions
    - Vendors: create, update, cancel their own auctions
    - Staff/Admin: full access
    """

    serializer_class = AuctionItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # FIX: Ensure 'product' is used consistently as the foreign key name
        qs = AuctionItem.objects.select_related(
            "product", "product__vendor", "product__vendor__user"
        ).prefetch_related("bids__user", "watchers", "comments")

        # PUBLIC + CUSTOMER (unauthenticated or authenticated but NOT vendor/admin)
        if not user.is_authenticated or not (user.is_staff or getattr(user, "role", None) == "VENDOR"):
            return qs.filter(status=AuctionItem.Status.ACTIVE, end_time__gt=timezone.now())

        # VENDOR: only own products
        if getattr(user, "role", None) == "VENDOR":
            return qs.filter(product__vendor__user=user) # Using 'product' here is correct

        # ADMIN: see everything
        return qs

    # --- CREATE AUCTION ---
    def perform_create(self, serializer):
        user = self.request.user
        # The key is 'product' which holds the VendorProduct instance
        product = serializer.validated_data["product"]

        # Only vendors can create auctions
        if getattr(user, "role", None) != "VENDOR":
            raise PermissionDenied("Only vendors can create auctions.")

        # Vendor must own the product
        if product.vendor.user != user:
            raise PermissionDenied("You can only auction your own products.")

        # Prevent auction if product is not in stock or already unavailable
        if product.stock <= 0 or not product.is_available:
            raise PermissionDenied("This product is not available for auction.")

        # Save auction
        auction = serializer.save(
            vendor=user,
            # Current bid starts at the start price
            current_bid=serializer.validated_data["start_price"],
            status=AuctionItem.Status.ACTIVE,
        )

        # Mark product unavailable (soft remove from VendorProduct)
        product.is_available = False
        product.save(update_fields=["is_available"])

        return auction

    # --- UPDATE AUCTION ---
    def perform_update(self, serializer):
        auction = self.get_object()
        user = self.request.user

        # Permission check using the correct 'product' relationship
        if not (user.is_staff or auction.product.vendor.user == user):
            raise PermissionDenied("You can only update your own auctions.")

        if auction.has_started():
            raise PermissionDenied("Cannot update an auction that has started.")

        serializer.save()

    # --- CANCEL AUCTION (SOFT DELETE) ---
    def perform_destroy(self, instance):
        user = self.request.user

        # Permission check using the correct 'product' relationship
        if not (user.is_staff or instance.product.vendor.user == user):
            raise PermissionDenied("You can only cancel your own auctions.")

        if instance.status != AuctionItem.Status.ACTIVE:
            raise PermissionDenied("Cannot cancel an ended or already cancelled auction.")

        # Soft cancel auction
        instance.status = AuctionItem.Status.CANCELLED
        instance.save(update_fields=["status"])

        # Restore product availability if auction is cancelled
        product = instance.product # Use 'product'
        product.is_available = True
        product.save(update_fields=["is_available"])

    # --- PLACE BID ---
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        serializer_class=BidSerializer,
    )
    def place_bid(self, request, pk=None):
        auction = self.get_object()
        MIN_INCREMENT = Decimal("1.00")

        data = request.data.copy()
        data["auction_id"] = str(auction.id)
        serializer = self.get_serializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data["amount"]
        max_bid = serializer.validated_data.get("max_bid", amount)
        user = request.user

        try:
            with transaction.atomic():
                # Lock auction row for concurrency safety
                auction = AuctionItem.objects.select_for_update().get(pk=auction.pk)

                if auction.status != AuctionItem.Status.ACTIVE or auction.end_time < timezone.now():
                    return Response(
                        {"detail": "Auction is no longer open for bidding."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                highest = auction.bids.order_by("-amount").first()
                current_high = highest.amount if highest else auction.start_price
                min_required_bid = current_high + MIN_INCREMENT

                if amount < min_required_bid:
                    raise ValidationError(
                        {
                            "amount": f"Bid must be at least {MIN_INCREMENT} higher than the current bid ({current_high}). Minimum required: {min_required_bid}"
                        }
                    )

                new_bid_amount = amount
                if highest and highest.user != user:
                    # FIX: Safely retrieve opponent_max, defaulting to their current bid if max_bid is NULL.
                    opponent_max = highest.max_bid if highest.max_bid is not None else highest.amount 
                    
                    if max_bid > opponent_max:
                        new_bid_amount = min(max_bid, opponent_max + MIN_INCREMENT)
                    elif max_bid == opponent_max:
                        new_bid_amount = opponent_max

                bid, _ = Bid.objects.update_or_create(
                    auction=auction, user=user, defaults={"amount": new_bid_amount, "max_bid": max_bid}
                )

                auction.current_bid = max(auction.current_bid, new_bid_amount)
                auction.save(update_fields=["current_bid"])

                # Send async bid notification
                send_bid_notification.delay(bid.id)

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except AuctionItem.DoesNotExist:
            return Response({"detail": "Auction item not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # FIX: Ensure logger is imported or defined
            # logger.error(f"Error placing bid on auction {pk}: {e}")
            return Response({"detail": "Internal error during bidding."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "detail": "Bid placed successfully.",
                "current_bid": auction.current_bid,
                "your_bid": new_bid_amount,
                "max_bid_set": max_bid,
            },
            status=status.HTTP_201_CREATED,
        )

    # --- DECLARE WINNER ---
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated], serializer_class=WinnerSerializer)
    def declare_winner(self, request, pk=None):
        auction = self.get_object()
        user = request.user

        # Permission check using the correct 'product' relationship
        if not (user.is_staff or auction.product.vendor.user == user):
            raise PermissionDenied("You can only declare a winner for your own auctions.")

        if auction.is_active():
            raise ValidationError("Cannot declare a winner before auction ends.")

        highest_bid = auction.bids.order_by("-amount").first()
        if not highest_bid:
            return Response({"detail": "No bids placed. Cannot declare a winner."}, status=status.HTTP_400_BAD_REQUEST)

        auction.winner = highest_bid.user
        auction.status = AuctionItem.Status.ENDED
        auction.save(update_fields=["winner", "status"])

        return Response(
            {"detail": f"The winner is {highest_bid.user.username}", "winning_bid": highest_bid.amount},
            status=status.HTTP_200_OK,
        )


class BidViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing bids.

    - Users can see their own bids.
    - Staff/Admin can see all bids.
    """
    serializer_class = BidSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            # Staff can see all bids
            return Bid.objects.select_related('auction', 'user').all()
        # Regular users see only their own bids
        return Bid.objects.select_related('auction').filter(user=user)


class WatchlistViewSet(viewsets.ModelViewSet):
    """
    Handles adding, removing, and viewing a user's auction watchlist.

    Buyers see the auctions they are watching.
    Vendors see users watching their auctions.
    
    Includes a toggle action to quickly watch or unwatch an auction.
    """
    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated, WatchlistPermission]

    def get_queryset(self):
        user = self.request.user
        if user.role != User.Roles.VENDOR:
            return Watchlist.objects.filter(user=user).select_related("auction", "auction__product")
        return Watchlist.objects.filter(auction__product__vendor=user).select_related(
            "user", "auction", "auction__product"
        )

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"detail": "This auction is already in your watchlist."})

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        """
        Toggle an auction in the user's watchlist (add/remove) using serializer validation.
        """
        user = request.user
        auction_id = request.data.get("auction")
        if not auction_id:
            return Response({"detail": "Auction ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Use serializer for validation
        serializer = self.get_serializer(data={"auction_id": auction_id})
        serializer.is_valid(raise_exception=True)
        auction = AuctionItem.objects.get(id=auction_id)

        # Atomic toggle
        watchlist_item, created = Watchlist.objects.get_or_create(user=user, auction=auction)
        if not created:
            watchlist_item.delete()
            return Response({"message": "Removed from watchlist.", "watched": False})

        return Response({"message": "Added to watchlist.", "watched": True})



class CommentViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD operations for comments on auction items.

    Permissions:
    - Customers: Can create, update, and delete their own comments.
    - Vendors: Read-only access to comments on their own auction items.
    """
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, CommentPermission]

    def get_queryset(self):
        """
        Returns filtered comments based on the user's role.
        - Customers: All non-deleted comments.
        - Vendors: Non-deleted comments related to auctions they own.
        Supports optional filtering by auction via query param ?auction=<id>
        """
        user = self.request.user
        queryset = Comment.objects.filter(is_deleted=False).select_related(
            "user", "auction", "auction__product"
        )

        # Filter for vendor's own auctions
        if user.role == User.Roles.VENDOR:
            queryset = queryset.filter(auction__product__vendor__user=user)

        # Optional auction filter
        auction_id = self.request.query_params.get("auction")
        if auction_id:
            queryset = queryset.filter(auction_id=auction_id)

        return queryset

    def perform_create(self, serializer):
        """
        Creates a new comment and automatically assigns the current user.
        """
        try:
            comment = serializer.save(user=self.request.user)
            send_comment_notification.delay(comment.id)
        except IntegrityError:
            raise ValidationError({"detail": "Unable to create comment at this time."})

    def perform_update(self, serializer):
        """
        Updates a comment.
        Ownership validation enforced by CommentPermission.
        """
        serializer.save()

    def perform_destroy(self, instance):
        """
        Soft-deletes a comment by setting is_deleted=True.
        """
        instance.is_deleted = True
        instance.save()

    @action(detail=True, methods=["post"])
    def toggle_delete(self, request, pk=None):
        """
        Toggle soft-delete on a comment:
        - If currently deleted, restores it.
        - If active, marks it as deleted.
        Only the comment owner can perform this action.
        """
        try:
            comment = Comment.objects.get(pk=pk, user=request.user)
        except Comment.DoesNotExist:
            return Response(
                {"detail": "Comment not found or you do not have permission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        comment.is_deleted = not comment.is_deleted
        comment.save()
        status_text = "deleted" if comment.is_deleted else "restored"
        return Response(
            {"message": f"Comment {status_text}.", "is_deleted": comment.is_deleted}
        )