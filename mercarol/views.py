from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from .serializers import *
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
from django.db.models import Q
from .permission import WatchlistPermission, CommentPermission
from .tasks import *
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema
import logging
from .filter import *
from rest_framework import filters
from django.urls import reverse_lazy
from django_filters.rest_framework import DjangoFilterBackend


logger = logging.getLogger('mercarol')

# core/views.py

from django.shortcuts import redirect
from django.contrib.auth import get_user_model

from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from rest_framework.parsers import MultiPartParser, FormParser

User = get_user_model()


class LoginOrSignupView(generics.GenericAPIView):
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
    """
    Manage product categories.
    • Only staff/superuser can create, update, or delete.
    • All authenticated users can read.
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()

    def _require_staff(self, action: str):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied(
                f"You do not have permission to {action} a category."
            )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)  # saves object
        return Response(
            {"message": f"Category '{serializer.data['name']}' created successfully"},
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
            status=status.HTTP_200_OK  # should be 200 for update
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
    Users can manage only their own vendor profile; staff/superusers have full access.
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
    queryset = VendorProduct.objects.all().select_related('vendor', 'vendor__user')

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
    One cart per user.
    POST adds / updates items (quantity merge).
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
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        serializer.save(cart=cart)



class OrderViewSet(viewsets.ModelViewSet):
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
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return ShippingAddress.objects.all()
        return ShippingAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PaymentViewSet(viewsets.ModelViewSet):
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


    # Deletes – only PENDING + own
  
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


#@extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
# class CheckoutViewSet(viewsets.ViewSet):
    
#     permission_classes = [IsAuthenticated]
#     serializer_class = CheckoutSerializer 
        

#     @extend_schema(
#         responses={201: OrderSerializer},
#     )
#     # def create(self, request, *args, **kwargs):
#     #     return super().create(request, *args, **kwargs)

#     def create(self, request):
#         user = request.user       
             
        
#         serializer = CheckoutSerializer(data=request.data, context={'request': request})
#         serializer.is_valid(raise_exception=True)

#         shipping = serializer.validated_data["shipping_address"]
#         print(shipping)
       
#         payment_method = serializer.validated_data["payment_method"]
#         delivery_note = serializer.validated_data.get("delivery_note", "")
        

       
#         # Get user's cart items
#         cart_items = CartItem.objects.filter(cart__user=user)
        
#         if not cart_items.exists():
#             raise ValidationError("Your cart is empty.")

#         # Create order
#         order = Order.objects.create(
#             user=user,
#             shipping=shipping,
#             total_price=sum([item.subtotal() for item in cart_items])
#         )

#         # Create order items
#         for item in cart_items:
#             OrderItem.objects.create(
#                 order=order,
#                 vendor_product=item.vendor_product,
#                 quantity=item.quantity,
#                 price=item.vendor_product.price,
#                 # price=item.subtotal
#             )

#         # Create payment
#         payment = Payment.objects.create(
#             # user=user,
#             order=order,
#             amount=order.total_price,
#             method=payment_method,
#             status=Payment.Status.PENDING,
#         )


#          # Clear the cart
#         cart_items.delete()
        

#         return Response({
#             "message": "Checkout completed successfully.",
#             "order_id": order.id,
#             "payment_id": payment.id,
#             "payment_status": payment.status
#         }, status=status.HTTP_201_CREATED)
# --- Example subtotal property in CartItem model ---
# class CartItem(models.Model):
#     quantity = models.PositiveIntegerField()
#     vendor_product = models.ForeignKey(VendorProduct, on_delete=models.CASCADE)
#
#     @property
#     def subtotal(self):
#         return self.quantity * self.vendor_product.price

@extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
class CheckoutViewSet(viewsets.ViewSet):
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


# class CheckoutViewSet(viewsets.ViewSet):
#     permission_classes = [IsAuthenticated]
#     serializer_class = CheckoutSerializer

#     def create(self, request):
#         user = request.user
#         serializer = CheckoutSerializer(data=request.data, context={'request': request})
#         serializer.is_valid(raise_exception=True)

#         shipping_address = serializer.validated_data["shipping_address"]
#         payment_method = serializer.validated_data["payment_method"]
#         delivery_note = serializer.validated_data.get("delivery_note", "")

#         # Get user's cart items
#         cart_items = CartItem.objects.filter(cart__user=user)
#         if not cart_items.exists():
#             raise ValidationError("Your cart is empty.")

#         # Calculate total
#         total_price = sum(item.subtotal() for item in cart_items)

#         try:
#             with transaction.atomic():
#                 # 1. Create the order
#                 order = Order.objects.create(
#                     user=user,
#                     shipping=shipping_address,
#                     total_price=total_price,
                
#                 )

#                 # 2. Create order items
#                 order_items = []
#                 for item in cart_items:
#                     if item.quantity > item.vendor_product.stock:
#                         raise ValidationError(
#                             f"Not enough stock for {item.vendor_product.name}"
#                         )
#                     order_items.append(
#                         OrderItem(
#                             order=order,
#                             vendor_product=item.vendor_product,
#                             quantity=item.quantity,
#                             price=item.vendor_product.price
#                         )
#                     )
#                 OrderItem.objects.bulk_create(order_items)

#                 # 3. Placeholder for payment integration
#                 # Here you would call your payment gateway API
#                 available_coins = user.coins
#                 if available_coins >= total_price:
                
#                     payment = Payment.objects.create(
#                         order=order,
#                         amount=total_price,
#                         method=payment_method,
#                         status=Payment.Status.PENDING  # Change after gateway success
#                     )
#                     user.coins = user.coins - total_price
#                 else:
#                     raise serializers.ValidationError({"details": "Insufficient balance"})

#                 # 4. Clear the cart
#                 cart_items.delete()

#         except ValidationError as e:
#             logger.warning(f"Checkout failed for user {user.id}: {str(e)}")
#             raise
#         except Exception as e:
#             logger.error(f"Unexpected error during checkout for user {user.id}: {str(e)}")
#             raise ValidationError("An unexpected error occurred during checkout.")

#         # 5. Return response
#         return Response({
#             "message": "Checkout completed successfully.",
#             "order_id": order.id,
#             "payment_id": payment.id,
#             "payment_status": payment.status
#         }, status=status.HTTP_201_CREATED)
       
        



class AuctionItemViewSet(viewsets.ModelViewSet):
    """
    - Public: List & retrieve active auctions
    - Vendors: Create, update, cancel their own auctions
    - Staff: Full access
    """
    queryset = AuctionItem.objects.all().select_related('product', 'winner')
    serializer_class = AuctionItemSerializer
    permission_classes = [IsAuthenticated]
    # filterset_fields = ['category', 'in_stock']

    # ------------------------------------------------------ #
    # 1. Public access for listing/retrieving
    # ------------------------------------------------------ #
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

    # ------------------------------------------------------ #
    # 2. Filter queryset by role
    # ------------------------------------------------------ #
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # Public (unauthenticated): only active, ongoing auctions
        if not user.is_authenticated or not (user.is_staff or getattr(user, 'role', None) == 'VENDOR'):
            return qs.filter(status=AuctionItem.Status.ACTIVE, end_time__gt=timezone.now())

        # Vendor: only their own auctions
        if getattr(user, 'role', None) == 'VENDOR':
            return qs.filter(product__vendor__user=user)

        # Staff: all auctions
        return qs

    # ------------------------------------------------------ #
    # 3. Create: only vendor, only for own product
    # ------------------------------------------------------ #
    def perform_create(self, serializer):
        user = self.request.user

        if getattr(user, 'role', None) != 'VENDOR':
            raise PermissionDenied("Only vendors can create auctions.")

        product = serializer.validated_data['product']
        if product.vendor != user:
            raise PermissionDenied("You can only auction your own products.")

        serializer.save(
            current_bid=serializer.validated_data['start_price'],
            status=AuctionItem.Status.ACTIVE
        )

    # ------------------------------------------------------ #
    # 4. Update: only before start, only by owner
    # ------------------------------------------------------ #
    def perform_update(self, serializer):
        auction = self.get_object()
        user = self.request.user

        if not (user.is_staff or auction.product.vendor.user == user):
            raise PermissionDenied("You can only update your own auctions.")

        if auction.has_started():
            raise PermissionDenied("Cannot update an auction that has started.")

        serializer.save()

    # ------------------------------------------------------ #
    # 5. Delete (soft cancel)
    # ------------------------------------------------------ #
    def perform_destroy(self, instance):
        user = self.request.user

        if not (user.is_staff or instance.product.vendor.user == user):
            raise PermissionDenied("You can only cancel your own auctions.")

        if instance.status != AuctionItem.Status.ACTIVE:
            raise PermissionDenied("Cannot cancel an ended or cancelled auction.")

        instance.status = AuctionItem.Status.CANCELLED
        instance.save(update_fields=['status'])

    # ------------------------------------------------------ #
    # 6. Place Bid
    # ------------------------------------------------------ #
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def place_bid(self, request, pk=None):
        auction = self.get_object()
        user = request.user

        if not auction.is_active():
            raise ValidationError("This auction is not active.")

        amount = request.data.get('amount')
        max_bid = request.data.get('max_bid', amount)

        # Validate bid inputs
        try:
            amount = float(amount)
            max_bid = float(max_bid)
        except (ValueError, TypeError):
            raise ValidationError("Invalid bid amount.")

        if amount <= 0:
            raise ValidationError("Bid must be greater than zero.")
        if amount > max_bid:
            raise ValidationError("Bid amount cannot exceed max bid.")

        # Check highest bid
        highest = auction.bids.order_by('-amount').first()
        current_high = highest.amount if highest else auction.start_price

        if amount <= current_high:
            raise ValidationError(f"Bid must be higher than current bid ({current_high}).")

        # Atomic transaction for concurrency safety
        with transaction.atomic():
            auction = AuctionItem.objects.select_for_update().get(pk=auction.pk)

            highest = auction.bids.order_by('-amount').first()
            current_high = highest.amount if highest else auction.start_price

            if amount <= current_high:
                raise ValidationError("Bid outpaced. Please try again.")

            # Proxy bidding
            new_bid_amount = amount
            if highest and highest.user != user:
                opponent_max = highest.max_bid
                if max_bid > opponent_max:
                    new_bid_amount = min(max_bid, opponent_max + 1)  # +1 increment

            bid, _ = Bid.objects.update_or_create(
                auction=auction,
                user=user,
                defaults={'amount': new_bid_amount, 'max_bid': max_bid}
            )

            auction.current_bid = max(auction.current_bid, new_bid_amount)
            auction.save(update_fields=['current_bid'])

        return Response({
            "detail": "Bid placed successfully.",
            "current_bid": auction.current_bid,
            "your_bid": new_bid_amount
        }, status=status.HTTP_201_CREATED)


class BidViewSet(viewsets.ModelViewSet):
    """
    Handles user bidding operations:
    - Each user can place one active bid per auction.
    - Supports proxy bidding with `max_bid`.
    - Ensures atomic updates to prevent race conditions.
    """
    queryset = Bid.objects.all()
    serializer_class = BidSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Limit users to view only their own bids."""
        user = self.request.user
        return (
            Bid.objects.filter(user=user)
            .select_related('auction', 'auction__product')
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        user = self.request.user
        auction = serializer.validated_data['auction']
        amount = serializer.validated_data['amount']
        max_bid = serializer.validated_data['max_bid']

        # --- 1. Auction must be active ---
        if not auction.is_active():
            raise ValidationError("This auction is not active or has ended.")

        # --- 2. Defensive check ---
        if max_bid < amount:
            raise ValidationError("Maximum bid must be at least equal to your initial bid.")

        # --- 3. Lock auction record ---
        with transaction.atomic():
            auction = AuctionItem.objects.select_for_update().get(pk=auction.pk)

            # Re-check after lock
            if not auction.is_active():
                raise ValidationError("Auction ended during bid placement.")

            # --- 4. Get current highest (exclude self) ---
            highest_bid = auction.bids.exclude(user=user).order_by('-amount').first()
            current_high = highest_bid.amount if highest_bid else auction.start_price

            # --- 5. Must beat current high ---
            if amount <= current_high:
                raise ValidationError(f"Bid must be higher than current bid ({current_high}).")

            # --- 6. Proxy bidding ---
            new_visible_bid = amount
            if highest_bid and (highest_bid.max_bid is None or max_bid > highest_bid.max_bid):
                new_visible_bid = min(max_bid, (highest_bid.max_bid or current_high) + 1)

            # --- 7. Save bid ---
            bid, created = Bid.objects.update_or_create(
                auction=auction,
                user=user,
                defaults={'amount': new_visible_bid, 'max_bid': max_bid},
            )
            process_bid.delay(bid.id)

            # --- 8. Update auction ---
            auction.current_bid = max(auction.current_bid, new_visible_bid)
            auction.save(update_fields=['current_bid'])

        serializer.instance = bid

    def create(self, request, *args, **kwargs):
        """Custom create method with user-friendly response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "success": True,
                "message": "Bid placed successfully.",
                "data": {
                    "bid": BidSerializer(serializer.instance).data,
                    "current_bid": serializer.instance.auction.current_bid,
                },
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )



class WatchlistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing watchlist items:
    - Customers: Full CRUD on their watchlist items.
    - Vendors: Read-only access to watchlists for their auctions.
    """
    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated, WatchlistPermission]

    def get_queryset(self):
        """
        Return queryset based on user role:
        - Customers: Their own watchlist items.
        - Vendors: Watchlist items for their auctions (via product.vendor).
        """
        user = self.request.user
        if user.role != User.Roles.VENDOR:
            return Watchlist.objects.filter(user=user).select_related("auction", "auction__product")
        return Watchlist.objects.filter(auction__product__vendor=user).select_related(
            "user", "auction", "auction__product"
        )

    def perform_create(self, serializer):
        """
        Create a watchlist item, auto-assigning the current user.
        Vendors are blocked by WatchlistPermission.
        """
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"detail": "This auction is already in your watchlist."})

    def perform_update(self, serializer):
        """
        Update a watchlist item. Vendors are blocked by WatchlistPermission.
        """
        serializer.save()

    def perform_destroy(self, instance):
        """
        Delete a watchlist item. Vendors are blocked by WatchlistPermission.
        """
        instance.delete()

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        """
        Toggle an auction in the user's watchlist (add/remove).
        """
        user = request.user
        auction_id = request.data.get("auction")
        if not auction_id:
            return Response({"detail": "Auction ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            auction = AuctionItem.objects.get(id=auction_id)
        except AuctionItem.DoesNotExist:
            return Response({"detail": "Auction not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if auction is active
        if not auction.is_active():
            return Response({"detail": "Cannot add inactive auction to watchlist."}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Atomic toggle to prevent race conditions
        watchlist_item, created = Watchlist.objects.get_or_create(user=user, auction=auction)
        if not created:  # Item exists, so remove it
            watchlist_item.delete()
            return Response({"message": "Removed from watchlist.", "watched": False})
        return Response({"message": "Added to watchlist.", "watched": True})

    @action(detail=True, methods=["post"])
    def move_to_cart(self, request, pk=None):
        """
        Move a watchlist item to the user's cart and remove it from the watchlist.
        """
        user = request.user

        with transaction.atomic():
            try:
                watch_item = Watchlist.objects.select_related("auction").get(id=pk, user=user)
            except Watchlist.DoesNotExist:
                return Response({"detail": "Watchlist item not found."}, 
                               status=status.HTTP_404_NOT_FOUND)

            auction = watch_item.auction

            # Check if auction is active or user is winner (if ended)
            if not auction.is_active():
                if auction.status == AuctionItem.Status.ENDED and auction.winner != user:
                    return Response({"detail": "Only the auction winner can add this to cart."}, 
                                   status=status.HTTP_403_FORBIDDEN)
                return Response({"detail": "Cannot add inactive auction to cart."}, 
                               status=status.HTTP_400_BAD_REQUEST)

            try:
                cart_item, created = CartItem.objects.get_or_create(
                    user=user,
                    auction=auction,
                    defaults={"quantity": 1},  # Remove if quantity is not applicable
                )
            except IntegrityError:
                return Response({"detail": "This auction is already in your cart."}, 
                               status=status.HTTP_400_BAD_REQUEST)

            watch_item.delete()

            return Response({
                "message": "Moved to cart.",
                "cart_item_id": cart_item.id,
            })
        


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
        """
        user = self.request.user

        queryset = Comment.objects.filter(is_deleted=False).select_related(
            "user", "auction"
        )

        if user.role == User.Roles.VENDOR:
            return queryset.filter(auction__product__vendor=user)

        return queryset

    def perform_create(self, serializer):
        """
        Creates a new comment and automatically assigns the current user.
        """
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({"detail": "Unable to create comment at this time."})

    def perform_update(self, serializer):
        """
        Updates a comment.
        Any ownership validation should be enforced by the permission class.
        """
        serializer.save()
       

    def perform_destroy(self, instance):
        """
        Performs a soft delete on the comment (sets is_deleted=True).
        """
        instance.delete()  # The model's delete() method should handle soft delete logic.
