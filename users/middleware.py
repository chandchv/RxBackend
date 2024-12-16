from django.shortcuts import redirect
from django.urls import reverse
from .models import Doctor, Patient

class RoleBasedRedirectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.path == '/' or request.path == '/dashboard/':
                try:
                    if Doctor.objects.filter(user=request.user).exists():
                        return redirect('users:doctor_dashboard')
                    elif Patient.objects.filter(user=request.user).exists():
                        return redirect('users:patient_dashboard')
                except:
                    pass

        response = self.get_response(request)
        return response 