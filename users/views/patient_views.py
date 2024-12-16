from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Patient, Doctor, Appointment
from ..forms import PatientForm
from ..serializers import PatientSerializer
from django.contrib import messages
from ..models import Patient, UserProfile

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
        
        # Get patient's appointments
        appointments = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).order_by('-appointment_date')
        
        # Get patient's prescriptions if you have prescription model
        prescriptions = []  # Replace with actual prescription query if available
        
        context = {
            'patient': patient,
            'appointments': appointments,
            'prescriptions': prescriptions,
            'doctor': doctor
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

