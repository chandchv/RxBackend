from django.shortcuts import render
from django.utils import timezone
from ..models import Billing, Appointment
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff, user_is_admin

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