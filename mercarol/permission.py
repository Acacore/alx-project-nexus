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
        if not user.is_vendor:
            return obj.user == user  # Customers can only access their comments
        return obj.auction.product.vendor == request.user  # Vendors can view their auctions’ comments