from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone
import uuid
from django_countries.fields import CountryField


from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.text import slugify
import uuid
from .managers import ActiveManager  



class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Roles.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        VENDOR = "VENDOR", "Vendor"
        CUSTOMER = "CUSTOMER", "Customer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)  # recommended unique
    phone_number = PhoneNumberField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to="profiles_images/", blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CUSTOMER)
    coins = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)  # Djoser likes this field

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # this is fine

    objects = CustomUserManager()

    def __str__(self):
        return self.email



class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        self.slug = slugify(self.name.lower())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name



class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="vendor_profile"
    )
    store_name = models.CharField(max_length=156)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="Images/vendor_logos/", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.store_name



class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE) # Have to be a Vendor
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="product",
    )
    image = models.ImageField(upload_to="Images/products", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        self.slug = slugify(self.name.lower())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class VendorProduct(models.Model):         
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="product")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="vendors_offers"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveBigIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)


    class Meta:
        unique_together = ("vendor", "product")

    def __str__(self):
        return f"{self.vendor.store_name} - {self.product.name}"


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor_product = models.ForeignKey(
        VendorProduct, on_delete=models.CASCADE, related_name="variant"
    )
    name = models.CharField(max_length=150)
    additional_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.vendor_product.product.name} - {self.name}"


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Cart {self.user.username}"


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="Items")
    vendor_product = models.ForeignKey(VendorProduct, on_delete=models.CASCADE)
    quantity = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def subtotal(self):
        return self.quantity * self.vendor_product.price

    def __str__(self):
        return f"Cart Itime {self.vendor_product} {self.quantity}"


class ShippingAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    delivery_note = models.CharField(max_length=526, blank=True, null=True)              
    address_line = models.CharField(max_length=128)
    city = models.CharField(max_length=100)
    postal_address = models.CharField(max_length=20)
    country = CountryField(blank_label="Select Country")
    phone = PhoneNumberField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.country}, {self.city}"



class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "pending"
        PAID = "PAID", "paid"
        SHIPPED = "SHIPPED", "shipped"
        DELIVERED = "DELIVERED", "delivered"
        CANCELLED = "CANCELLED", "canceled"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    shipping = models.ForeignKey(ShippingAddress, on_delete=models.CASCADE, related_name='order')
    name = models.CharField(max_length=128, blank=True, null=True) 
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Order #{self.id} of {self.user.username}"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="order_items"
    )
    vendor_product = models.ForeignKey(
        VendorProduct,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField(default=1)   
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def subtotal(self):
        return self.quantity * self.price


class Payment(models.Model):
    class Mode(models.TextChoices):
        COINS = "COINS", "coins"
        ZELLE = "ZELLE", "zelle"
        CARD = "CARD", "card"

    class Status(models.TextChoices):
        PENDING = "PENDING", "pending"
        COMPLETED = "COMPLETED", "completed"
        FAILED = "FAILED", "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "Order", on_delete=models.CASCADE, related_name="payment"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Mode, default=Mode.COINS)
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    vendor_payment_status = models.CharField(
        max_length=20,
        choices=[("PENDING", "pending"), ("DISBURSED", "disbursed")],
        default="PENDING",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Payment {self.transaction_id} for Order {self.order.id}"


class AuctionItem(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ENDED = "ENDED", "Ended"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(
        VendorProduct, on_delete=models.CASCADE, related_name="auction"
    )
    start_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_bid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reserve_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    is_deleted = models.BooleanField(default=False)
    winner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_auctions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # objects = ActiveManager()       # default filtered (is_deleted=False)
    # all_objects = models.Manager() 
    
    class Meta:
        verbose_name = "Auction Item"
        verbose_name_plural = "Auction Items"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Auction: {self.product} | Current: {self.current_bid} | Ends: {self.end_time:%b %d, %H:%M}"

    def is_active(self):
        """Check if the auction is still active."""
        return self.status == self.Status.ACTIVE and timezone.now() < self.end_time

    def has_started(self):
        """Helper: check if auction has started."""
        return timezone.now() >= self.start_time


class Bid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(
        "AuctionItem", on_delete=models.CASCADE, related_name="bids"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bids")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Current visible bid amount"
    )
    max_bid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Maximum amount user is willing to pay (proxy bidding)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("auction", "user")  # One active bid per user per auction
        ordering = ["-created_at"]
        verbose_name = "Bid"
        verbose_name_plural = "Bids"

    def __str__(self):
        username = self.user.role or self.user.username
        return f"Bid by {username} on {self.auction.product} | {self.amount} ({self.max_bid})"

    def save(self, *args, **kwargs):
        """
        Override save for possible future hooks.
        Leave empty since auction updates are managed in the ViewSet
        with atomic transactions for concurrency safety.
        """
        super().save(*args, **kwargs)


class Watchlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="watchlist_items"
    )
    auction = models.ForeignKey(
        AuctionItem, on_delete=models.CASCADE, related_name="watchers"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "auction")
        ordering = ["-added_at"]
        verbose_name = "Watchlist Item"
        verbose_name_plural = "Watchlist Items"

    def __str__(self):
        return f"{self.user.username} → {self.auction.product.product.name}"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="auction_comments"
    )
    auction = models.ForeignKey(
        AuctionItem, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Comment"
        verbose_name_plural = "Comments"

    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}{'...' if len(self.content) > 50 else ''}"

    def delete(self, *args, **kwargs):
        # Soft delete
        self.is_deleted = True
        self.save()



