from rest_framework import permissions

class IsClinicAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_superuser or 
             (hasattr(request.user, 'staff') and request.user.staff.role == 'ADMIN'))
        ) 