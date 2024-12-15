from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..models import Doctor, Appointment
from django.db.models import Q

@login_required
def dashboard_view(request):
    print("\n=== DASHBOARD VIEW STARTED ===")
    
    # Get all verified doctors - remove any additional filters
    doctors = Doctor.objects.all()
    print(f"Total doctors in database: {doctors.count()}")
    
    # Print raw doctor data
    for doc in doctors:
        print(f"Doctor in DB - ID: {doc.id}, Name: {doc.name}, Verified: {doc.verified}")
    
    # Format the doctors list
    formatted_doctors = []
    for doctor in doctors:
        doctor_info = {
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization or 'General Practice',
            'medical_council': doctor.medical_council,
            'license_number': doctor.license_number
        }
        formatted_doctors.append(doctor_info)
        print(f"Formatted doctor: {doctor_info}")
    
    # Get appointments
    appointments = Appointment.objects.filter(
        Q(patient__user=request.user) | Q(doctor__user=request.user)
    ).order_by('-appointment_date')
    
    context = {
        'doctors': formatted_doctors,
        'appointments': appointments,
    }
    
    print(f"Number of doctors being sent to template: {len(formatted_doctors)}")
    print("=== DASHBOARD VIEW COMPLETED ===\n")
    
    return render(request, 'dashboard.html', context) 