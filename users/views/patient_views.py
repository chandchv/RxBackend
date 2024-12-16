from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Patient, Doctor, Appointment, Prescription
from ..forms import AppointmentForm, PatientForm, AppointmentForm_patient
from ..serializers import PatientSerializer
from django.contrib import messages
from ..models import Patient, UserProfile
from django.utils import timezone

@login_required
def create_patient(request):
    try:
        # Get the clinic from the logged-in user's profile
        user_profile = UserProfile.objects.get(user=request.user)
        clinic = user_profile.clinic
        
        if request.method == 'POST':
            try:
                patient = Patient.objects.create(
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    date_of_birth=request.POST['date_of_birth'],
                    gender=request.POST['gender'],
                    phone_number=request.POST['phone_number'],
                    email=request.POST.get('email', ''),
                    address=request.POST.get('address', ''),
                    pincode=request.POST.get('pincode', ''),
                    clinic=clinic
                )
                messages.success(request, 'Patient added successfully!')
                return redirect('users:patients_list')
            except Exception as e:
                print(f"Error creating patient: {str(e)}")
                messages.error(request, f'Error adding patient: {str(e)}')
        
        return render(request, 'doctor/create_patient.html')
    
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in create_patient view: {str(e)}")
        messages.error(request, 'Error accessing patient creation')
        return redirect('users:dashboard')

@login_required
def patients_list(request):
    try:
        # Get the clinic from the logged-in user's profile
        user_profile = UserProfile.objects.get(user=request.user)
        clinic = user_profile.clinic
        
        # Get all patients for this clinic
        patients = Patient.objects.filter(clinic=clinic).order_by('-created_at')
        
        return render(request, 'doctor/patients.html', {
            'patients': patients
        })
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error fetching patients: {str(e)}")
        messages.error(request, 'Error fetching patients list')
        return redirect('users:dashboard')

@login_required
def patient_detail(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Get all appointments for this patient with this doctor
        appointments = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).order_by('-appointment_date')
        
        # Get all prescriptions for this patient from this doctor
        prescriptions = Prescription.objects.filter(
            doctor=doctor,
            patient=patient
        ).order_by('-date')
        
        context = {
            'patient': patient,
            'appointments': appointments,
            'prescriptions': prescriptions,
            'doctor': doctor,
            'total_appointments': appointments.count(),
            'total_prescriptions': prescriptions.count(),
        }
        
        return render(request, 'doctor/patient_detail.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found')
        return redirect('users:patients_list')

@login_required
def patient_edit(request, patient_id):
    try:
        # Get the clinic from the logged-in user's profile
        user_profile = UserProfile.objects.get(user=request.user)
        clinic = user_profile.clinic
        
        # Get the patient
        patient = get_object_or_404(Patient, id=patient_id, clinic=clinic)
        
        if request.method == 'POST':
            # Update patient information
            patient.first_name = request.POST.get('first_name')
            patient.last_name = request.POST.get('last_name')
            patient.date_of_birth = request.POST.get('date_of_birth')
            patient.gender = request.POST.get('gender')
            patient.phone_number = request.POST.get('phone_number')
            patient.email = request.POST.get('email')
            patient.address = request.POST.get('address')
            patient.pincode = request.POST.get('pincode')
            patient.save()
            
            messages.success(request, 'Patient information updated successfully!')
            return redirect('users:patient_detail', patient_id=patient.id)
        
        return render(request, 'doctor/patient_edit.html', {'patient': patient})
    
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found')
        return redirect('users:dashboard')
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found')
        return redirect('users:patients_list')
    except Exception as e:
        print(f"Error editing patient: {str(e)}")
        messages.error(request, 'Error updating patient information')
        return redirect('users:patients_list')

@login_required
def doctor_create_appointment(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            form = AppointmentForm(request.POST)
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.doctor = doctor
                appointment.status = 'scheduled'
                
                # Check if the selected time slot is available
                if Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=appointment.appointment_date
                ).exists():
                    messages.error(request, 'This time slot is already booked. Please select another time.')
                else:
                    appointment.save()
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:doctor_appointments')
        else:
            form = AppointmentForm(initial={'doctor': doctor})

        context = {
            'form': form,
            'doctor': doctor,
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'doctor/create_appointment.html', context)

    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('users:dashboard')

@login_required
def patient_create_appointment(request):
    try:
        patient = Patient.objects.get(patient_id=request.user.id)
        
        if request.method == 'POST':
            form = AppointmentForm(request.POST)
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.patient = patient
                appointment.status = 'scheduled'
                
                # Check if the selected time slot is available
                if Appointment.objects.filter(
                    doctor=appointment.doctor,
                    appointment_date=appointment.appointment_date
                ).exists():
                    messages.error(request, 'This time slot is already booked. Please select another time.')
                else:
                    appointment.save()
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:patient_appointments')
        else:
            form = AppointmentForm()

        context = {
            'form': form,
            'patient': patient,
            'doctors': Doctor.objects.all(),
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'patient/create_appointment.html', context)

    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('users:dashboard')

@login_required
def patient_dashboard(request):
    try:
        patient = Patient.objects.get(user=request.user)
        
        # Get upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__gte=timezone.now(),
            status='scheduled'
        ).order_by('appointment_date')

        # Get past appointments
        past_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__lt=timezone.now()
        ).order_by('-appointment_date')

        # Get recent prescriptions
        recent_prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-date')[:5]

        context = {
            'patient': patient,
            'upcoming_appointments': upcoming_appointments,
            'past_appointments': past_appointments,
            'recent_prescriptions': recent_prescriptions,
            'total_appointments': upcoming_appointments.count(),
            'total_prescriptions': recent_prescriptions.count(),
        }
        
        return render(request, 'patient/dashboard.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:login')

@login_required
def patient_prescriptions(request):
    try:
        patient = Patient.objects.get(user=request.user)
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-date')
        
        context = {
            'patient': patient,
            'prescriptions': prescriptions,
        }
        
        return render(request, 'patient/prescriptions.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:login')

