from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from ..models import Doctor, Staff, Patient, Appointment
from ..decorators import user_is_admin

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

@login_required
@user_is_admin
def billing_overview(request):
    # Logic for admin's billing overview
    context = {
        'total_patients': 0,  # Replace with actual logic
        'total_appointments': 0,  # Replace with actual logic
        'total_billing': 0,  # Replace with actual logic
    }
    return render(request, 'admin/billing_overview.html', context) 