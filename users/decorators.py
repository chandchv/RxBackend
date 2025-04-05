from django.core.exceptions import PermissionDenied
from functools import wraps
from django.contrib.auth.decorators import user_passes_test

def user_is_doctor(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'doctor'):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def user_is_staff(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return user_passes_test(lambda u: u.is_authenticated)(view_func)(request, *args, **kwargs)
            
        if not hasattr(request.user, 'staff'):
            raise PermissionDenied("You don't have staff access")
            
        if not request.user.staff.clinic:
            raise PermissionDenied("No clinic assigned to your account")
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def user_is_admin(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view 