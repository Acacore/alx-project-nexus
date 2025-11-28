from rest_framework import permissions
from rest_framework.permissions import BasePermission
from .models import User


class WatchlistPermission(BasePermission):
    """
    Permission class for WatchlistViewSet:
    - Customers: Full CRUD on their own watchlist items.
    - Vendors: Read-only access to watchlist items for their auctions.
    """
    def has_permission(self, request, view):
        # Ensure user is authenticated
        user = request.user
        if not user.is_authenticated:
            return False
        # Vendors can only perform safe methods (GET, HEAD, OPTIONS)
        if  user.role == User.Roles.VENDOR and request.method not in ["GET", "HEAD", "OPTIONS"]:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        # Customers can only access their own watchlist items
        user = request.user
        if not user.role == User.Roles.VENDOR :
            return obj.user == request.user
        # Vendors can only view watchlist items for their auctions
        return obj.auction.product.vendor == user
    


class CommentPermission(BasePermission):
    """
    Permission class for CommentViewSet:
    - Customers: Full CRUD on their own comments.
    - Vendors: Read-only access to comments on their auctions.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.role == User.Roles.VENDOR and request.method not in ["GET", "HEAD", "OPTIONS"]:
            return False  # Vendors can’t create/edit/delete
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.role == 'vendor':
            return obj.user == user  # Customers can only access their comments
        return obj.auction.product.vendor == request.user  # Vendors can view their auctions’ comments



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



class IsCustomer(BasePermission):
    """
    Allows access only to users whose role = 'customer'.
    """

    def has_permission(self, request, view):
        # If user is not authenticated, block
        if not request.user or request.user.is_anonymous:
            return False

        # Check the user's role
        return getattr(request.user, "role", None) == User.Roles.CUSTOMER
