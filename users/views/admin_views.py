from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from ..models import Doctor, Staff, Patient, Appointment

@login_required
def admin_dashboard(request):
    # Get the user's clinic
    clinic = request.user.userprofile.clinic
    
    context = {
        'doctors_count': Doctor.objects.filter(clinic=clinic).count(),
        'staff_count': Staff.objects.filter(clinic=clinic).count(),
        'patients_count': Patient.objects.filter(clinic=clinic).count(),
        'todays_appointments': Appointment.objects.filter(
            doctor__clinic=clinic,
            appointment_date__date=timezone.now().date()
        ).count(),
    }
    
    return render(request, 'clinic_admin/admin_dashboard.html', context) 