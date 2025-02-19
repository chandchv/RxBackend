from .models import Doctor
import json
from django.conf import settings

def doctor_info(request):
    if request.user.is_authenticated and hasattr(request.user, 'is_doctor') and request.user.is_doctor:
        try:
            doctor = Doctor.objects.get(user=request.user)
            print(f"Doctor found: {doctor}, Clinic: {doctor.clinic}, Logo: {doctor.clinic.logo}")  # Debug print
            return {'doctor': doctor}
        except Doctor.DoesNotExist:
            print("Doctor does not exist")  # Debug print
            pass
    return {'doctor': None}

def firebase_config(request):
    return {
        'FIREBASE_CONFIG': json.dumps(settings.FIREBASE_CONFIG)
    } 