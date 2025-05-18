from django.shortcuts import render
from django.utils import timezone
from ..models import Billing, Appointment, Patient, Doctor, Prescription, LabTest
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff, user_is_admin
from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect

@login_required
@user_is_staff
def generate_report(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.filter(appointment_date__gte=start_of_month).count()
    total_billing = Billing.objects.filter(created_at__gte=start_of_month).aggregate(total=models.Sum('amount'))['total'] or 0

    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_billing': total_billing,
    }

    return render(request, 'reports/monthly_report.html', context) 

@login_required
@user_is_admin
def admin_billing_overview(request):
    # Admin-specific billing overview logic
    ... 

@login_required
def doctor_report_overview(request):
    """View for showing doctor's report overview"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Get statistics for the current month
        today = timezone.now()
        first_day = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get appointments statistics
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=first_day,
            appointment_date__lte=today
        )
        
        total_appointments = appointments.count()
        completed_appointments = appointments.filter(status='completed').count()
        cancelled_appointments = appointments.filter(status='cancelled').count()
        
        # Get patient statistics
        total_patients = Patient.objects.filter(
            appointment__doctor=doctor
        ).distinct().count()
        
        new_patients = Patient.objects.filter(
            appointment__doctor=doctor,
            created_at__gte=first_day
        ).distinct().count()
        
        # Get prescription statistics
        prescriptions = Prescription.objects.filter(
            doctor=doctor,
            date__gte=first_day,
            date__lte=today
        )
        
        total_prescriptions = prescriptions.count()
        
        # Get lab test statistics
        lab_tests = LabTest.objects.filter(
            prescription__doctor=doctor,
            created_at__gte=first_day,
            created_at__lte=today
        )
        
        total_lab_tests = lab_tests.count()
        completed_lab_tests = lab_tests.filter(status='COMPLETED').count()
        
        context = {
            'doctor': doctor,
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'total_patients': total_patients,
            'new_patients': new_patients,
            'total_prescriptions': total_prescriptions,
            'total_lab_tests': total_lab_tests,
            'completed_lab_tests': completed_lab_tests,
            'current_month': today.strftime('%B %Y')
        }
        
        return render(request, 'doctor/report_overview.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in doctor_report_overview: {str(e)}")
        messages.error(request, 'Error accessing report overview')
        return redirect('users:doctor_dashboard') 