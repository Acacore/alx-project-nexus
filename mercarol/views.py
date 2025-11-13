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
from django.db.models import Q


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
            raise PermissionDenied(
                f"You do not have permission to {action} a category."
            )

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
        if getattr(self.request.user, "role", None) != "VENDOR":
            raise PermissionDenied("You do not have permission to create a product.")
        vendor = self._get_vendor()
        serializer.save(vendor=vendor)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            serializer.save()
            return
        if getattr(user, "role", None) != "VENDOR":
            raise PermissionDenied("You do not have permission to update a product.")
        self._check_vendor_ownership(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            instance.delete()
            return
        if getattr(user, "role", None) != "VENDOR":
            raise PermissionDenied("You do not have permission to delete a product.")
        self._check_vendor_ownership(instance)
        instance.delete()


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
        if getattr(user, "role", None) == User.Roles.VENDOR:
            return queryset.filter(vendor__user=user)

        # Others see nothing
        return VendorProduct.objects.none()

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

        # Admins can do everything
        if user.is_staff or user.is_superuser:
            serializer.save()
            return

        if getattr(user, "role", None) != User.Roles.VENDOR:
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

        if getattr(user, "role", None) != User.Roles.VENDOR:
            raise PermissionDenied("Only vendors can delete vendor products.")

        if instance.vendor.user != user:
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

        # One cart per user
        cart, created = Cart.objects.get_or_create(user=user)

        if not created:
            # Existing cart → add / update item
            vp_id = self.request.data.get("Vendor_product")
            qty = int(self.request.data.get("quantity", 1))

            if not vp_id:
                raise ValidationError({"Vendor_product": "This field is required."})

            try:
                item = cart.Items.get(Vendor_product_id=vp_id)
                item.quantity += qty
                item.save()
            except CartItem.DoesNotExist:
                CartItem.objects.create(
                    cart=cart, Vendor_product_id=vp_id, quantity=qty
                )
            return  # skip serializer.save()

        # New cart
        serializer.save(user=user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own cart.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own cart.")
        instance.delete()


class CartItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Users can only **view** their own cart items.
    All mutations must go through `/cart/`.
    """

    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only items belonging to the current user's cart
        return CartItem.objects.filter(cart__user=self.request.user)


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
    """
    * Regular users → create / edit / delete **only** the shipping address
      of **their own pending order**.
    * Staff / superuser → full access.
    """

    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]
    queryset = ShippingAddress.objects.all()

    # Base queryset – filtered per role

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(order__user=user)

    # Pass request to serializer (needed for validation)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # Helper – ownership + pending status in ONE place

    def _check_ownership_and_pending(self, instance: ShippingAddress, action: str):
        user = self.request.user
        order = instance.order

        if user.is_staff or user.is_superuser:
            return

        if order.user != user:
            raise PermissionDenied(
                f"You do not have permission to {action} this shipping address."
            )
        if order.status != Order.Status.PENDING:
            raise PermissionDenied(
                f"Cannot {action} a shipping address for a processed order."
            )

    # CREATE – serializer already validated everything

    def perform_create(self, serializer):
        serializer.save()

    # UPDATE – extra safety (serializer already checked order)

    def perform_update(self, serializer):
        self._check_ownership_and_pending(serializer.instance, "update")
        serializer.save()

    # 6. DESTROY – same safety as update

    def perform_destroy(self, instance):
        self._check_ownership_and_pending(instance, "delete")
        instance.delete()




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




class AuctionViewSet(viewsets.ModelViewSet):
    """
    - Public: List & retrieve active auctions
    - Vendors: Create, update, cancel their own auctions
    - Staff: Full access
    """
    queryset = AuctionItem.objects.all().select_related('product', 'winner')
    serializer_class = AuctionSerializer
    permission_classes = [IsAuthenticated]

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
        if product.vendor.user != user:
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
