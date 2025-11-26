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




class CommentPermission(permissions.BasePermission):
    """
    Custom permission for comments:
    - Customers can create, update, and delete their own comments.
    - Vendors can only read comments on their own auctions.
    """

    def has_permission(self, request, view):
        # Allow authenticated users to use the view
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Safe methods (GET, HEAD, OPTIONS) are allowed for everyone who can view
        if request.method in permissions.SAFE_METHODS:
            if user.role == user.Roles.VENDOR:
                # Vendors can only view comments on their own auctions
                return obj.auction.product.vendor == user
            return True  # Customers can view all comments

        # For unsafe methods (POST, PUT, PATCH, DELETE):
        # Only the owner of the comment can modify or delete it
        return obj.user == user
