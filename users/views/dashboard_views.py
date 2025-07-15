from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth.models import User
from ..models import Doctor, Patient, Appointment, Staff, ActivityLog, LabTest, ClinicAdmin
from labs.models import LabProfile
from datetime import datetime, timedelta
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

@login_required
def doctor_dashboard(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        
        # Get lab tests that need doctor review (status='COMPLETED')
        completed_lab_tests = LabTest.objects.filter(
            prescription__doctor=request.user,
            status='COMPLETED'
        ).select_related(
            'prescription',
            'prescription__patient',
            'test_definition'
        ).order_by('-updated_at')
        
        context = {
            'doctor': doctor,
            'today_date': today,
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
            ).count(),
            'completed_lab_tests': completed_lab_tests
        }
        return render(request, 'doctor/dashboard.html', context)
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found. Please contact your administrator.')
        return redirect('users:login')



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
    # Get the user from the request
    user = request.user
    
    # Log user information
    logger.info(f"User {getattr(user, 'username', user.email)} accessing dashboard redirect")
    
    # First check if user is authenticated
    if not user.is_authenticated:
        logger.warning("Unauthenticated user attempting to access dashboard")
        return redirect('users:login')
        
    # Check if user is a superuser
    if user.is_superuser:
        logger.info(f"Superuser {user.username or user.email} redirecting to superuser dashboard")
        return redirect('users:superuser_dashboard')
        
    # Check if user is a staff member
    try:
        staff = Staff.objects.filter(user=user).first()
        if staff:
            logger.info(f"Staff user {user.username or user.email} redirecting to staff dashboard")
            return redirect('users:staff_dashboard')
    except Exception as e:
        logger.error(f"Error checking staff status: {str(e)}")
    
    # Check if user is a doctor
    try:
        # Use filter and first instead of get to avoid exceptions
        doctor = Doctor.objects.filter(user=user).first()
        if doctor and doctor.verified:  # Only redirect if doctor is verified
            logger.info(f"Doctor {doctor.name} redirecting to doctor dashboard")
            return redirect('users:doctor_dashboard')
        elif doctor and not doctor.verified:
            logger.warning(f"Unverified doctor {doctor.name} attempting to access dashboard")
            messages.warning(request, 'Your doctor profile is pending verification. Please contact your administrator.')
            return redirect('users:login')
    except Exception as e:
        logger.error(f"Error checking doctor status: {str(e)}")
    
    # Check if user is a patient
    try:
        # Use filter and first instead of get to avoid exceptions
        patient = Patient.objects.filter(user=user).first()
        if patient:
            logger.info(f"Patient redirecting to patient dashboard")
            return redirect('users:patient_dashboard')
    except Exception as e:
        logger.error(f"Error checking patient status: {str(e)}")
    
    # Check if user is a clinic admin
    try:
        clinic_admin = ClinicAdmin.objects.filter(user=user).first()
        if clinic_admin:
            logger.info(f"Clinic admin {user.username or user.email} redirecting to clinic admin dashboard")
            return redirect('users:clinic_admin_dashboard')
    except Exception as e:
        logger.error(f"Error checking clinic admin status: {str(e)}")
    
    # Check if user is a lab user
    try:
        # First check if user has a direct lab profile (main lab user)
        lab_profile = LabProfile.objects.filter(user=user).first()
        if lab_profile:
            if lab_profile.is_approved:
                logger.info(f"Lab user {user.username or user.email} redirecting to lab dashboard")
                return redirect('labs:lab_dashboard')
            else:
                logger.warning(f"Unapproved lab user {user.username or user.email} attempting to access dashboard")
                messages.warning(request, 'Your lab account is pending approval. Please contact your administrator.')
                return redirect('users:login')
        
        # Check if user is a lab staff member (additional lab users)
        from labs.models import LabUser as LabUserModel
        lab_user = LabUserModel.objects.filter(user=user, is_active=True).first()
        if lab_user:
            if lab_user.lab_profile.is_approved:
                logger.info(f"Lab staff user {user.username or user.email} redirecting to lab dashboard")
                return redirect('labs:lab_dashboard')
            else:
                logger.warning(f"Lab staff user {user.username or user.email} attempting to access unapproved lab")
                messages.warning(request, 'The lab you are associated with is pending approval. Please contact your administrator.')
                return redirect('users:login')
    except Exception as e:
        logger.error(f"Error checking lab status: {str(e)}")
    
    # If no role is found, redirect to a default page
    logger.warning(f"No role found for user {user}")
    messages.warning(request, 'No user profile found. Please complete your profile.')
    return redirect('users:profile_setup')

# Add a new view for profile setup
def profile_setup(request):
    from ..models import Clinic
    
    if request.method == 'POST':
        # Handle profile creation
        try:
            # Validate date format
            date_of_birth = request.POST.get('date_of_birth')
            if not date_of_birth:
                messages.error(request, 'Date of birth is required')
                return render(request, 'patient/profile_setup.html')
            
            # Get clinic - either from form or default to first available clinic
            clinic_id = request.POST.get('clinic')
            if clinic_id:
                try:
                    clinic = Clinic.objects.get(id=clinic_id)
                except Clinic.DoesNotExist:
                    messages.error(request, 'Selected clinic not found')
                    return render(request, 'patient/profile_setup.html')
            else:
                # Default to first available clinic
                clinic = Clinic.objects.first()
                if not clinic:
                    messages.error(request, 'No clinics available. Please contact administrator.')
                    return render(request, 'patient/profile_setup.html')
                
            patient = Patient.objects.create(
                user=request.user,
                clinic=clinic,  # Add the required clinic field
                first_name=request.POST.get('first_name', request.user.first_name),
                last_name=request.POST.get('last_name', request.user.last_name),
                date_of_birth=date_of_birth,
                gender=request.POST.get('gender'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email', request.user.email),
                address=request.POST.get('address'),
                pincode=request.POST.get('pincode')
            )
            messages.success(request, 'Profile created successfully!')
            return redirect('users:patient_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating profile: {str(e)}')
    
    # Get available clinics for the form
    clinics = Clinic.objects.all()
    return render(request, 'patient/profile_setup.html', {'clinics': clinics}) 