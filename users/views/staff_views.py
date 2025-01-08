from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from django.shortcuts import redirect
from ..forms import StaffAppointmentForm
from ..models import Appointment

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

@login_required
def staff_create_appointment(request):
    try:
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Access denied.')
            return redirect('users:dashboard')

        clinic = request.user.clinic if hasattr(request.user, 'clinic') else None
        
        if request.method == 'POST':
            form = StaffAppointmentForm(request.POST, clinic=clinic)
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.status = 'scheduled'
                
                # Get form data
                appointment_date = form.cleaned_data['appointment_date']
                appointment_time = datetime.strptime(request.POST.get('appointment_time'), '%H:%M').time()
                
                # Check if the selected time slot is available
                existing_appointment = Appointment.objects.filter(
                    doctor=appointment.doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status='scheduled'
                ).exists()
                
                if existing_appointment:
                    messages.error(request, 'This time slot is already booked. Please select another time.')
                else:
                    appointment.appointment_time = appointment_time
                    appointment.save()
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:dashboard')
            else:
                messages.error(request, 'Invalid form submission. Please check the data.')
                print("Form errors:", form.errors)  # For debugging
        else:
            form = StaffAppointmentForm(clinic=clinic)

        context = {
            'form': form,
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'clinic_admin/create_appointment.html', context)

    except Exception as e:
        print(f"Error in staff_create_appointment: {str(e)}")
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('users:dashboard') 