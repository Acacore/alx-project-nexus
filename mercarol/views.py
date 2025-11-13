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
from rest_framework.exceptions import PermissionDenied, ValidationError
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
        if obj.user != self.request.user and not (self.request.user.is_staff or self.request.user.is_superuser):
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

    """
    A simple ViewSet for viewing and managing Vendor.
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
    Manage product categories.
    • Only staff/superuser can create, update, or delete.
    • All authenticated users can read.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()

    def _require_staff(self, action: str):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied(f"You do not have permission to {action} a category.")

    def perform_create(self, serializer):
        self._require_staff("create")
        serializer.save()

    def perform_update(self, serializer):
        self._require_staff("update")
        serializer.save()

    def perform_destroy(self, instance):
        self._require_staff("delete")
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    """
    Vendors can manage only their own products.
    Staff/superusers have full access.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()

    def _get_vendor(self):
        """Safely get Vendor instance for the user."""
        try:
            return self.request.user.vendor
        except AttributeError:
            raise PermissionDenied("You do not have a vendor profile.")

    def _check_vendor_ownership(self, product):
        """Ensure product belongs to the user's vendor."""
        if product.vendor != self._get_vendor():
            raise PermissionDenied("You can only manage your own products.")

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Product.objects.all()
        try:
            return Product.objects.filter(vendor=user.vendor)
        except AttributeError:
            return Product.objects.none()  # no vendor → no products

    def perform_create(self, serializer):
        if getattr(self.request.user, 'role', None) != "VENDOR":
            raise PermissionDenied("You do not have permission to create a product.")
        vendor = self._get_vendor()
        serializer.save(vendor=vendor)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            serializer.save()
            return
        if getattr(user, 'role', None) != "VENDOR":
            raise PermissionDenied("You do not have permission to update a product.")
        self._check_vendor_ownership(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            instance.delete()
            return
        if getattr(user, 'role', None) != "VENDOR":
            raise PermissionDenied("You do not have permission to delete a product.")
        self._check_vendor_ownership(instance)
        instance.delete()


class VendorProductViewSet(viewsets.ModelViewSet):
    """
    Vendors can manage their own VendorProduct items.
    Staff and superusers have full access.
    """
    serializer_class = VendorProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = VendorProduct.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = VendorProduct.objects.all()

        # Optional filters
        vendor_name = self.request.query_params.get("vendor")
        product_id = self.request.query_params.get("id")

        if vendor_name:
            queryset = queryset.filter(vendor__name__icontains=vendor_name)
        if product_id:
            try:
                queryset = queryset.filter(id=int(product_id))
            except (ValueError, TypeError):
                pass

        # Admins see everything
        if user.is_staff or user.is_superuser:
            return queryset

        # Vendors see only their own products
        if getattr(user, 'role', None) == User.Roles.VENDOR:
            return queryset.filter(vendor__user=user)

        # Others see nothing
        return VendorProduct.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        if getattr(user, 'role', None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can create vendor products.")

        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("You don’t have a vendor profile yet.")

        serializer.save(vendor=vendor)

    def perform_update(self, serializer):
        user = self.request.user

        # Admins can do everything
        if user.is_staff or user.is_superuser:
            serializer.save()
            return

        if getattr(user, 'role', None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can update vendor products.")

        if serializer.instance.vendor.user != user:
            raise PermissionDenied("You can only update your own vendor products.")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user

        # Admins can do everything
        if user.is_staff or user.is_superuser:
            instance.delete()
            return

        if getattr(user, 'role', None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can delete vendor products.")

        if instance.vendor.user != user:
            raise PermissionDenied("You can only delete your own vendor products.")

        instance.delete()


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    Vendors can manage their own product variants.
    Staff and superusers have full access.
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

        if product_id and str(product_id).isdigit():
            queryset = queryset.filter(vendor_product__id=int(product_id))

        # Admins see everything
        if user.is_staff or user.is_superuser:
            return queryset

        # Vendors see only their own variants
        if getattr(user, 'role', None) == User.Roles.VENDOR:
            return queryset.filter(vendor_product__vendor__user=user)

        # Everyone else sees nothing (safer default)
        return ProductVariant.objects.none()


class CartViewSet(viewsets.ModelViewSet):
    """
    Users can manage only their own cart.
    One cart per user. Adding a product updates quantity if already in cart.
    """
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    queryset = Cart.objects.all()

    def get_queryset(self):
        """Return the cart(s) for the logged-in user."""
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user

        # Prevent overriding the user field
        if 'user' in self.request.data:
            raise ValidationError({"user": "You cannot set the user field."})

        # Get or create the user's cart
        cart, created = Cart.objects.get_or_create(user=user)

        # If the cart already exists, update item quantity
        if not created:
            variant_id = self.request.data.get("product_variant")
            quantity = self.request.data.get("quantity", 1)

            if not variant_id:
                raise ValidationError({"product_variant": "This field is required."})

            try:
                quantity = int(quantity)
            except (ValueError, TypeError):
                raise ValidationError({"quantity": "Quantity must be a valid number."})

            # Update existing item or create new one
            item, _ = cart.items.get_or_create(product_variant_id=variant_id, defaults={'quantity': quantity})
            if not _:
                item.quantity += quantity
                item.save()

            return  # Don't save serializer, already handled

        # If new cart, save serializer with user
        serializer.save(user=user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own cart.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own cart.")
        instance.delete()


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
    queryset = Order.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(user=user)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_destroy(self, instance):
        if instance.status != Order.Status.PENDING:
            raise PermissionDenied("Cannot delete a processed order.")
        instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
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
        if (
            not hasattr(order, "payment")
            or order.payment.status != Payment.Status.COMPLETED
        ):
            raise PermissionDenied("Order does not have a completed payment.")

        # Check if vendor's products are in the order
        vendor_products = VendorProduct.objects.filter(vendor=vendor).values_list(
            "id", flat=True
        )
        if not OrderItem.objects.filter(
            order=order, vendor_product__id__in=vendor_products
        ).exists():
            raise PermissionDenied(
                "You are not associated with any products in this order."
            )

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
    queryset = OrderItem.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = OrderItem.objects.all()
        # Filter by vendor_product_id if provided
        vendor_product_id = self.request.query_params.get("vendor_product_id")
        if vendor_product_id:
            queryset = queryset.filter(vendor_product_id=vendor_product_id)
        # Admin can see all items
        if user.is_staff or user.is_superuser:
            return queryset
        # Role-based filtering
        if hasattr(user, "role"):
            if user.role == "CUSTOMER":
                return queryset.filter(order__user=user)
            elif user.role == "VENDOR":
                return queryset.filter(vendor_product__vendor__user=user)
        return queryset.none()  # Empty queryset for users without a role

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save()  # Validation handled by OrderItemSerializer

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.order.status != Order.Status.PENDING:
            raise PermissionDenied(
                "Cannot delete an order item from a processed order."
            )
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied(
                "You do not have permission to delete this order item."
            )
        instance.delete()


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]
    queryset = ShippingAddress.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = ShippingAddress.objects.all()
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        # Validation is handled by the serializer, so just save
        serializer.save()

    def perform_update(self, serializer):
        # Ensure the user can only update their own shipping address
        user = self.request.user
        instance = self.get_object()
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied(
                "You do not have permission to update this shipping address."
            )
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied(
                "Cannot update a shipping address for a processed order."
            )
        serializer.save()

    def perform_destroy(self, instance):
        # Ensure the user can only delete their own shipping address
        user = self.request.user
        if not (user.is_staff or user.is_superuser or instance.order.user == user):
            raise PermissionDenied(
                "You do not have permission to delete this shipping address."
            )
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied(
                "Cannot delete a shipping address for a processed order."
            )
        instance.delete()


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]
    queryset = ShippingAddress.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = ShippingAddress.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied(
                "Cannot update a shipping address for a processed order."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.order.status != instance.order.Status.PENDING:
            raise PermissionDenied(
                "Cannot delete a shipping address for a processed order."
            )
        instance.delete()


# class PaymentViewSet(viewsets.ModelViewSet):
#     serializer_class = PaymentSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         user = self.request.user
#         queryset = Payment.objects.all()
#         if user.is_staff:
#             return queryset
#         return queryset.filter(order__user=user)

#     def get_serializer_context(self):
#         return {'request': self.request}

#     def perform_update(self, serializer):
#         instance = self.get_object()
#         if instance.status != Payment.Status.PENDING:
#             raise PermissionDenied("Cannot update a completed or failed payment.")
#         serializer.save()

#     def perform_destroy(self, instance):
#         if instance.status != Payment.Status.PENDING:
#             raise PermissionDenied("Cannot delete a completed or failed payment.")
#         instance.delete()


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.all()
        if user.is_staff:
            return queryset
        return queryset.filter(order__user=user)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status != Payment.Status.PENDING:
            raise PermissionDenied("Cannot update a completed or failed payment.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Payment.Status.PENDING:
            raise PermissionDenied("Cannot delete a completed or failed payment.")
        instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def confirm_vendor_payment(self, request, pk=None):
        """
        Allows a vendor to confirm their payment portion is received (sets vendor_payment_status=DISBURSED).
        """
        payment = self.get_object()
        user = request.user

        # Check if user is a vendor
        try:
            vendor = Vendor.objects.get(user=user)
        except Vendor.DoesNotExist:
            raise PermissionDenied("You are not a vendor.")

        # Check if vendor's products are in the order
        vendor_products = VendorProduct.objects.filter(vendor=vendor).values_list(
            "id", flat=True
        )
        if not OrderItem.objects.filter(
            order=payment.order, vendor_product__id__in=vendor_products
        ).exists():
            raise PermissionDenied("You are not associated with this order.")

        # Check if payment is COMPLETED
        if payment.status != Payment.Status.COMPLETED:
            raise PermissionDenied("Payment must be completed.")

        # Mark vendor payment as DISBURSED
        payment.vendor_payment_status = "DISBURSED"
        payment.save()

        serializer = self.get_serializer(payment)
        return Response(serializer.data)
