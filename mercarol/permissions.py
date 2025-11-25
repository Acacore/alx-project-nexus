from rest_framework import permissions
from .models import User

class IsAdminOrVendorOwner(permissions.BasePermission):
    """
    - Admin: full access
    - Vendor: CRUD only on their own products
    - Customer: read-only
    """

    def has_permission(self, request, view):
        # Everyone can read
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        # Only admin and vendor can write
        return user.is_authenticated and (user.is_superuser or user.role == User.Roles.VENDOR)

    def has_object_permission(self, request, view, obj):
        # Read-only always allowed
        if request.method in permissions.SAFE_METHODS:
            return True

        # Admin can do anything
        if request.user.is_staff:
            return True

        # Vendor can modify only their own auction
        return obj.product.vendor == request.user
