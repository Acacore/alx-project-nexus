from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid
from django_countries.fields import CountryField




class User(AbstractBaseUser):

    class Roles(models.TextChoices):
        ADMIN = "ADMIN", _("Admin")
        VENDOR = "VENDOR", _("Vendor")
        CUSTOMER = "CUSTOMER", _("Customer")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=False, blank=False)
    phone_number = PhoneNumberField(blank=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to="profiles_images", blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CUSTOMER)
    coins = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    # For authentication purpose
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        # ordering = ["-date_created"]


class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_profile')
    store_name = models.CharField(max_length=156)
    description = models.TextField(blank=True)
    logo=models.ImageField(upload_to='Images/vendor_logos/', blank=True, null=True)
    created_at=models.DateTimeField(default=timezone.now)


    def __str__(self):
        return self.store_name
    
class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name=models.CharField(max_length=100, unique=True)
    slug=models.SlugField(unique=True)

    def __str__(self):
        return self.name
    

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name=models.CharField(max_length=200)
    slug=models.SlugField(unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='product')
    image= models.ImageField(upload_to="Images/products")
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name
    

class VendorProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='product')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='vendors_offers')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveBigIntegerField(default=0)
    is_available=models.BooleanField(default=True)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    

    class Meta:
        unique_together = ('vendor', 'product')
    
    def __str__(self):
        return f"{self.vendor.store_name} - {self.product.name}"


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor_product= models.ForeignKey(VendorProduct, on_delete=models.CASCADE, related_name='variant')
    name= models.CharField(max_length=150)
    additional_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f"{self.vendor_product.product.name} - {self.name}"


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user= models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at=models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Cart {self.user.username}"
    

class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart=models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='Items')
    Vendor_product = models.ForeignKey(VendorProduct, on_delete=models.CASCADE)
    quantity = models.PositiveBigIntegerField(default=1)

    def subtotal(self):
        return self.quatity * self.Vendor_product.price


    def __str__(self):
        return f"Cart Itime {self.Vendor_product} {self.quantity}"

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', ('pending')
        PAID = 'PAID', ('paid')
        SHIPPED = 'SHIPPED', ('shipped')
        DELIVERED = 'DELIVERED', ('delivered')
        CANCELLED = 'CANCELLED', ('canceled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='Items')
    created_at=models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    

    def __str__(self):
        return f"Order #{self.id} of {self.user.username}"
    


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='Items')
    VendorProduct = models.ForeignKey(VendorProduct, on_delete=models.CASCADE,)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)


    def subtotal(self):
        return self.quatity * self.Vendor_product.price
    

class ShippingAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping')
    reciever = models.CharField(max_length=156)
    address_line = models.CharField(max_length=128)
    city = models.CharField(max_length=100)
    postal_address=models.CharField(max_length=20)
    country = CountryField(blank_label='Select Country')
    phone = PhoneNumberField()

    def __str__(self):
        return f"{self.reciever}, {self.city}"
    

class Payement(models.Model):
    class Mode(models.TextChoices):
        COINS = 'COINS', ('coins')
        ZELLE = 'ZELLE', ('zelle')
        CARD = 'CARD', ('card')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payement')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(choices=Mode, default=Mode.COINS)
    trasaction_id = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    

    def __str__(self):
        return f"{self.customer.username} pays {self.amount}"
    


      


