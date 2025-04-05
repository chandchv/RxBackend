from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import DoctorAvailability, Patient, Doctor, Appointment, Prescription, PatientVitals
from ..forms import AppointmentForm, PatientForm, AppointmentForm_patient
from ..serializers import PatientSerializer
from django.contrib import messages
from ..models import Patient, UserProfile
from django.utils import timezone
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
@login_required
def create_patient(request):
    try:
        # Get the doctor and their associated clinic
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        
        if request.method == 'POST':
            try:
                # Create patient with the data from the form
                patient = Patient.objects.create(
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    date_of_birth=request.POST['date_of_birth'],
                    gender=request.POST['gender'],
                    blood_group=request.POST.get('blood_group'),  # Optional field
                    phone_number=request.POST['phone_number'],
                    email=request.POST.get('email', ''),  # Optional field
                    address=request.POST.get('address', ''),  # Optional field
                    pincode=request.POST.get('pincode', ''),  # Optional field
                    clinic=clinic  # Set the clinic from the doctor's clinic
                )
                messages.success(request, 'Patient added successfully!')
                return redirect('users:patients_list')
            except Exception as e:
                print(f"Error creating patient: {str(e)}")
                messages.error(request, f'Error adding patient: {str(e)}')
        
        return render(request, 'doctor/create_patient.html')
    
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in create_patient view: {str(e)}")
        messages.error(request, 'Error accessing patient creation')
        return redirect('users:dashboard')

@login_required
def patients_list(request):
    try:
        # Check if user is admin/staff
        if request.user.is_staff or request.user.is_superuser:
            # Staff can see all patients
            patients = Patient.objects.all().order_by('-created_at')
            context = {
                'patients': patients,
                'total_patients': patients.count(),
                'is_staff': True
            }
        else:
            # Regular doctor sees only their clinic's patients
            doctor = Doctor.objects.get(user=request.user)
            patients = Patient.objects.filter(clinic=doctor.clinic).order_by('-created_at')
            context = {
                'patients': patients,
                'doctor': doctor,
                'total_patients': patients.count(),
                'is_staff': False
            }
        
        return render(request, 'doctor/patients_list.html', context)
        
    except Doctor.DoesNotExist:
        if request.user.is_staff or request.user.is_superuser:
            # If staff user doesn't have a doctor profile, still show all patients
            patients = Patient.objects.all().order_by('-created_at')
            context = {
                'patients': patients,
                'total_patients': patients.count(),
                'is_staff': True
            }
            return render(request, 'doctor/patients_list.html', context)
        else:
            messages.error(request, 'Doctor profile not found')
            return redirect('users:dashboard')
@csrf_exempt
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
def patient_create_appointment(request):
    try:
        patient = Patient.objects.get(user=request.user)
        
        if request.method == 'POST':
            form = AppointmentForm_patient(request.POST)
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.patient = patient
                appointment.status = 'scheduled'
                
                # Get form data
                appointment_date = form.cleaned_data['appointment_date']
                appointment_time = form.cleaned_data['appointment_time']
                
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
                    appointment.save()
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:patient_dashboard')
            else:
                messages.error(request, 'Invalid form submission. Please check the data.')
                print("Form errors:", form.errors)  # For debugging
        else:
            form = AppointmentForm_patient()

        context = {
            'form': form,
            'patient': patient,
            'doctors': Doctor.objects.filter(clinic=patient.clinic),
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'patient/create_appointment.html', context)

    except Patient.DoesNotExist:
        messages.error(request, 'Access denied. Patient profile not found.')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in patient_create_appointment: {str(e)}")
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

        # Get previous appointments (including completed, cancelled, and missed)
        previous_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__lt=timezone.now()
        ).exclude(
            status='scheduled'
        ).order_by('-appointment_date')

        # Get recent prescriptions
        recent_prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-date')[:5]

        context = {
            'patient': patient,
            'upcoming_appointments': upcoming_appointments,
            'previous_appointments': previous_appointments,
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
    """View for listing all prescriptions of a patient"""
    try:
        # Get the patient associated with the logged-in user
        patient = Patient.objects.get(user=request.user)
        
        # Get all prescriptions for this patient, ordered by date
        prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-created_at')
        
        context = {
            'patient': patient,
            'prescriptions': prescriptions,
        }
        
        return render(request, 'patient/prescriptions.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:login')
    except Exception as e:
        print(f"Error in patient_prescriptions: {str(e)}")
        messages.error(request, 'Error accessing prescriptions')
        return redirect('users:patient_dashboard')

@login_required
def prescription_detail(request, pk):
    """View for showing details of a specific prescription"""
    try:
        # Get the prescription first
        prescription = get_object_or_404(
            Prescription.objects.select_related(
                'doctor',
                'doctor__user',
                'doctor__clinic',
                'patient',
                'patient__user'
            ).prefetch_related('items'),
            id=pk
        )
        
        # Check if user is authorized to view this prescription
        if hasattr(request.user, 'patient'):
            # User is a patient
            patient = request.user.patient
            if prescription.patient != patient:
                messages.error(request, 'You are not authorized to view this prescription.')
                return redirect('users:patient_dashboard')
        elif hasattr(request.user, 'doctor'):
            # User is a doctor
            doctor = request.user.doctor
            if prescription.doctor != doctor:
                messages.error(request, 'You are not authorized to view this prescription.')
                return redirect('users:doctor_dashboard')
        else:
            messages.error(request, 'Access denied.')
            return redirect('users:login')
        
        # Get the latest vitals for this patient
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient
        ).order_by('-recorded_at').first()
        
        context = {
            'prescription': prescription,
            'vitals': vitals,
            'patient': prescription.patient,
            'today': timezone.now(),
            'is_doctor': hasattr(request.user, 'doctor')
        }
        
        # Use different templates for doctors and patients
        template_name = 'doctor/prescription_detail.html' if hasattr(request.user, 'doctor') else 'patient/prescription_detail.html'
        return render(request, template_name, context)
        
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found.')
        if hasattr(request.user, 'doctor'):
            return redirect('users:doctor_dashboard')
        return redirect('users:patient_dashboard')
    except Exception as e:
        print(f"Error in prescription_detail: {str(e)}")
        messages.error(request, f'Error accessing prescription: {str(e)}')
        if hasattr(request.user, 'doctor'):
            return redirect('users:doctor_dashboard')
        return redirect('users:patient_dashboard')

@login_required
def patient_medical_history(request):
    try:
        patient = Patient.objects.get(user=request.user)
        
        # Get all past appointments
        past_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__lt=timezone.now().date()
        ).order_by('-appointment_date')
        
        # Get all prescriptions
        prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-date')
        
        context = {
            'patient': patient,
            'past_appointments': past_appointments,
            'prescriptions': prescriptions,
        }
        
        return render(request, 'patient/medical_history.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:dashboard')

@login_required
def patient_profile(request):
    try:
        patient = Patient.objects.get(user=request.user)
        if request.method == 'POST':
            # Handle profile updates here
            patient.phone = request.POST.get('phone', patient.phone)
            patient.address = request.POST.get('address', patient.address)
            patient.save()
            messages.success(request, 'Profile updated successfully')
            return redirect('users:patient_profile')
            
        context = {
            'patient': patient,
        }
        return render(request, 'patient/profile.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:dashboard')

@login_required
@require_http_methods(["GET"])
def get_available_slots_patient(request, doctor_id, date):
    """API endpoint to get available slots for a doctor on a specific date"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get doctor's availability for the selected day
        day_of_week = selected_date.weekday()
        availability = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_available=True
        ).first()
        
        if not availability:
            return JsonResponse({
                'slots': [],
                'message': 'Doctor not available on this day'
            })
        
        # Get booked appointments for this date
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status='scheduled'
        ).values_list('appointment_time', flat=True)
        
        # Generate available slots
        available_slots = []
        start_time = availability.start_time
        end_time = availability.end_time
        
        # Generate slots in 30-minute intervals
        current_slot = datetime.combine(selected_date, start_time)
        end_datetime = datetime.combine(selected_date, end_time)
        
        while current_slot < end_datetime:
            slot_time = current_slot.time()
            if slot_time not in booked_slots:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M'),
                    'available': True
                })
            current_slot += timedelta(minutes=30)
        
        return JsonResponse({
            'slots': available_slots,
            'doctor_name': doctor.name,
            'date': date
        })
        
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

