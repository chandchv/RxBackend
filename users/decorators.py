from django.core.exceptions import PermissionDenied

def user_is_doctor(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'doctor'):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def user_is_staff(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def user_is_admin(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view 