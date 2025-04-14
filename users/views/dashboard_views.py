from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import Doctor, Patient, Appointment, Staff, ActivityLog
from datetime import datetime, timedelta
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

@login_required
def doctor_dashboard(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        
        context = {
            'doctor': doctor,
            'today_appointments': Appointment.objects.filter(
                doctor=doctor,
                appointment_date=today
            ).order_by('appointment_time'),
            'today_appointments_count': Appointment.objects.filter(
                doctor=doctor,
                appointment_date=today
            ).count(),
            'total_patients': Patient.objects.filter(clinic=doctor.clinic).count(),
            'pending_appointments': Appointment.objects.filter(
                doctor=doctor,
                status='scheduled'
            ).count()
        }
        return render(request, 'doctor/dashboard.html', context)
    except Doctor.DoesNotExist:
        return redirect('users:dashboard')



@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('users:dashboard')
    
    today = timezone.now().date()
    
    context = {
        'total_doctors': Doctor.objects.count(),
        'total_patients': Patient.objects.count(),
        'total_staff': Staff.objects.count(),
        'today_appointments': Appointment.objects.filter(
            appointment_date=today
        ).count(),
        'recent_activities': ActivityLog.objects.all().order_by('-timestamp')[:10]
    }
    return render(request, 'doctor/admin/dashboard.html', context)

@login_required
def dashboard_redirect(request):
    """Redirects users to their appropriate dashboard based on their role"""
    logger.info(f"User {request.user.username} accessing dashboard redirect")
    
    # First check if user is authenticated
    if not request.user.is_authenticated:
        logger.warning("Unauthenticated user attempting to access dashboard")
        return redirect('login')
        
    # Check if user is a superuser
    if request.user.is_superuser:
        logger.info(f"Superuser {request.user.username} redirecting to superuser dashboard")
        return redirect('users:superuser_dashboard')
        
    # Check if user is a staff member
    if hasattr(request.user, 'staff'):
        logger.info(f"Staff user {request.user.username} redirecting to staff dashboard")
        return redirect('users:staff_dashboard')
        
    # Check if user is a doctor
    try:
        doctor = Doctor.objects.get(user=request.user)
        logger.info(f"Doctor {doctor.name} redirecting to doctor dashboard")
        return redirect('users:doctor_dashboard')
    except Doctor.DoesNotExist:
        logger.debug(f"User {request.user.username} is not a doctor")
    
    # Check if user is a patient
    try:
        patient = Patient.objects.get(user=request.user)
        logger.info(f"Patient {patient.get_full_name()} redirecting to patient dashboard")
        return redirect('users:patient_dashboard')
    except Patient.DoesNotExist:
        logger.warning(f"User {request.user.username} has no associated patient profile")
    
    # Check if user is a clinic admin
    if hasattr(request.user, 'clinicadmin'):
        logger.info(f"Clinic admin {request.user.username} redirecting to clinic admin dashboard")
        return redirect('users:clinic_admin_dashboard')
    
    # Check if user is a lab user
    if hasattr(request.user, 'lab_profile'):
        logger.info(f"Lab user {request.user.username} redirecting to lab dashboard")
        if request.user.lab_profile.is_approved:
            return redirect('labs:lab_dashboard')
        else:
            messages.error(request, 'Your lab account is not yet approved.')
    
    # If no role is found, redirect to a default page
    logger.warning(f"No role found for user {request.user.username}")
    messages.warning(request, 'No user profile found. Please contact support.')
    return redirect('users:profile_setup')

# Add a new view for profile setup
def profile_setup(request):
    if request.method == 'POST':
        # Handle profile creation
        try:
            patient = Patient.objects.create(
                user=request.user,
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                date_of_birth=request.POST.get('date_of_birth'),
                gender=request.POST.get('gender'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email'),
                address=request.POST.get('address'),
                pincode=request.POST.get('pincode')
            )
            messages.success(request, 'Profile created successfully!')
            return redirect('users:patient_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating profile: {str(e)}')
    
    return render(request, 'patient/profile_setup.html') 