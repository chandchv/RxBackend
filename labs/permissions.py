from rest_framework import permissions
from .models import LabOrder

class IsLabOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission to only allow lab owners or staff to upload results for their orders.
    """
    def has_permission(self, request, view):
        # Check if user is authenticated and has a lab profile
        if not request.user.is_authenticated or not hasattr(request.user, 'lab_profile'):
            return False
        
        # Staff users can access all
        if request.user.is_staff:
            return True
            
        # For POST requests, check order ownership
        if request.method == 'POST':
            order_id = request.data.get('order_id')
            if not order_id:
                return False
                
            try:
                order = LabOrder.objects.get(id=order_id)
                return order.chosen_lab == request.user.lab_profile
            except LabOrder.DoesNotExist:
                return False
                
        return True 