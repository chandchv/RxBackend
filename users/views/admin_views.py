from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.utils import timezone
from ..models import Doctor, Staff, Patient, Appointment
from ..decorators import user_is_admin
from django.db.models import Count
from labs.models import LabProfile, LabOrder, LabResult
from django.core.exceptions import PermissionDenied
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

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
        'total_patients': Patient.objects.count() or 0,  # Replace with actual logic
        'total_appointments': Appointment.objects.count() or 0,  # Replace with actual logic
        'total_billing': 0,  # Replace with actual logic
    }
    return render(request, 'billing/admin/billing_dashboard.html', context) 

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def superuser_dashboard(request):
    """Superuser dashboard showing all system statistics and management options"""
    if not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to access this page.")
    
    try:
        # Lab Statistics
        lab_stats = {
            'total_labs': LabProfile.objects.count(),
            'approved_labs': LabProfile.objects.filter(is_approved=True).count(),
            'pending_labs': LabProfile.objects.filter(is_approved=False).count(),
            'total_orders': LabOrder.objects.count(),
            'pending_orders': LabOrder.objects.filter(status='pending').count(),
            'completed_orders': LabOrder.objects.filter(status='completed').count(),
        }
        
        # User Statistics - Handle database schema changes gracefully
        user_stats = {
            'total_doctors': Doctor.objects.count(),
            'total_patients': Patient.objects.count(),
            'total_staff': Staff.objects.count(),
            'active_doctors': Doctor.objects.filter(is_active=True).count(),
            'active_patients': Patient.objects.count(),
        }
        
        # Health Records Statistics (if available)
        health_stats = {
            'total_records': 0,
            'records_by_type': [],
        }
        
        try:
            from HealthRecords.models import HealthRecord
            health_stats = {
                'total_records': HealthRecord.objects.count(),
                'records_by_type': HealthRecord.objects.values('record_type').annotate(count=Count('id')),
            }
        except ImportError:
            logger.warning("HealthRecords app not available")
        
        # Recent Activity
        try:
            recent_activity = {
                'lab_orders': LabOrder.objects.order_by('-order_date')[:5],
                'labs': LabProfile.objects.order_by('-created_at')[:5],
                'doctors': Doctor.objects.order_by('-created_at')[:5],
            }
        except Exception as e:
            logger.error(f"Error fetching recent activity: {str(e)}")
            recent_activity = {
                'lab_orders': [],
                'labs': [],
                'doctors': [],
            }
        
        context = {
            'lab_stats': lab_stats,
            'user_stats': user_stats,
            'health_stats': health_stats,
            'recent_activity': recent_activity,
        }
        
        return render(request, 'admin/superuser_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in superuser dashboard: {str(e)}")
        messages.error(request, "An error occurred while loading the dashboard. Please try again later.")
        return redirect('users:dashboard') 