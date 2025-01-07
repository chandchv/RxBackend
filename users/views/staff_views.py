from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff

@login_required
@user_is_staff
def billing_overview(request):
    # Logic for staff billing overview
    context = {
        'total_patients': 0,  # Replace with actual logic
        'total_appointments': 0,  # Replace with actual logic
        'total_billing': 0,  # Replace with actual logic
    }
    return render(request, 'staff/billing_overview.html', context) 