from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
# Create your models here.


class Users(AbstractBaseUser):
    class Roles(models.TextChoices):
        ADMIN = "ADMIN", _("Admin")
        VENDOR = "VENDOR", _("Vendor")
        CUSTOMER = "CUSTOMER", _("Customer")

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=False, blank=False)
    phone_number = PhoneNumberField(blank=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to="profiles_images", blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CUSTOMER)

    # For authentication purpose
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        # ordering = ["-date_created"]


   