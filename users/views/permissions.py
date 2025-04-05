from rest_framework import permissions

class IsStaff(permissions.BasePermission):
    """
    Custom permission to only allow staff members to access the view.
    """
    def has_permission(self, request, view):
        # Check if the user is authenticated and has a staff profile
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, 'staff')) 