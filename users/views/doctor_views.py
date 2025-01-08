from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Doctor, Appointment, Patient, DoctorAvailability, AppointmentSlot, DoctorLeave, Billing
from ..serializers import DoctorSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from ..scripts.scrapeGpt01 import verify_doctor as verify_doctor_api
import json
from django.db.models import Q
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Count
from ..forms import AppointmentForm, DoctorAvailabilityForm
from django.core.exceptions import ValidationError
from ..decorators import user_is_doctor
from django.db import models

class DoctorCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            print("Received data:", request.data)  # Debug print
            
            serializer = DoctorSerializer(data={
                'license_number': request.data.get('license_number'),
                'medical_council': request.data.get('medical_council'),
                'specialization': request.data.get('specialization', ''),
            })
            
            if serializer.is_valid():
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)  # Debug print
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"Error creating doctor: {str(e)}")
            return Response(
                {'error': f'Failed to create doctor profile: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class DoctorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctors = Doctor.objects.all()
        serializer = DoctorSerializer(doctors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DoctorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
            serializer = DoctorSerializer(doctor)
            return Response(serializer.data)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Doctor profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

@login_required
def verify_doctor_api_view(request):
    """API endpoint for doctor verification"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = verify_doctor_api(
                name=data.get('name'),
                registration_number=data.get('registration_number'),
                state_council=data.get('state_council')
            )
            
            return JsonResponse({
                'verified': result.get('verified', False),
                'name': result.get('name'),
                'registration_number': result.get('registration_number'),
                'state_council': result.get('state_council'),
                'qualification': result.get('qualification', ''),
                'registration_date': result.get('registration_date', '')
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'verified': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'verified': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'verified': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def save_doctor(request):
    if request.method == 'POST':
        try:
            verified_data_str = request.POST.get('verified_data', '')
            if not verified_data_str:
                raise ValueError("No verification data provided")

            verified_data = json.loads(verified_data_str)
            print("\nDEBUG: Save Doctor Process")
            print("Received verified data:", verified_data)
            
            # Create or update Doctor record
            doctor, created = Doctor.objects.update_or_create(
                license_number=verified_data.get('registration_number', ''),
                defaults={
                    'name': verified_data.get('name', ''),
                    'medical_council': verified_data.get('state_council', ''),
                    'verified': True,  # Explicitly set to True
                    'specialization': verified_data.get('qualification', ''),
                }
            )
            
            print(f"DEBUG: Doctor {'created' if created else 'updated'}")
            print(f"DEBUG: Doctor details - Name: {doctor.name}, Verified: {doctor.verified}")

            messages.success(request, 'Doctor profile saved successfully!')
            return redirect('users:dashboard')

        except json.JSONDecodeError as e:
            print("JSON Decode Error:", str(e))
            print("Received data:", request.POST.get('verified_data', ''))
            messages.error(request, 'Error processing verification data')
        except Exception as e:
            print("General Error:", str(e))
            messages.error(request, f'Error saving doctor profile: {str(e)}')
        
        return redirect('users:verify_doctor')

    return redirect('users:verify_doctor')

def get_doctors_list(request):
    try:
        doctors = Doctor.objects.all()
        doctors_list = []
        
        for doctor in doctors:
            doctors_list.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization or 'General Practice',
                'medical_council': doctor.medical_council,
                'license_number': doctor.license_number
            })
        
        print(f"Returning {len(doctors_list)} doctors")  # Debug print
        return JsonResponse({'doctors': doctors_list})
    except Exception as e:
        print(f"Error in get_doctors_list: {str(e)}")  # Debug print
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def doctor_dashboard_view(request):
    # Get all doctors
    doctors = Doctor.objects.all()
    print(f"Total doctors in database: {doctors.count()}")
    
    # Get today's appointments
    today = date.today()
    today_appointments = Appointment.objects.filter(
        appointment_date__date=today
    ).order_by('appointment_date')
    
    total_patients = Patient.objects.count()
    pending_appointments = Appointment.objects.filter(status='pending').count()
    
    # Format doctors for the template
    formatted_doctors = [
        {
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization or 'General Practice',
            'medical_council': doctor.medical_council,
            'license_number': doctor.license_number
        }
        for doctor in doctors
    ]
    
    context = {
        'doctors': formatted_doctors,
        'today_appointments': today_appointments,
        'total_patients': total_patients,
        'pending_appointments': pending_appointments,
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def doctor_appointments_view(request):
    try:
        # Get the doctor's appointments
        doctor = Doctor.objects.get(user=request.user)
        appointments = Appointment.objects.filter(doctor=doctor).order_by('appointment_date')
        
        return render(request, 'doctor/appointments.html', {
            'appointments': appointments
        })
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:doctor_dashboard')
    except Exception as e:
        print(f"Error fetching appointments: {str(e)}")
        messages.error(request, 'Error accessing appointments')
        return redirect('users:doctor_dashboard')


@login_required
def create_appointment(request):
    try:
        print(f"User ID: {request.user.id}")  # Debug print
        doctor = Doctor.objects.filter(user=request.user).first()
        
        if not doctor:
            print("Doctor not found for user")  # Debug print
            messages.error(request, 'Doctor profile not found. Please complete your profile setup.')
            return redirect('users:doctor_profile')
            
        print(f"Doctor found: {doctor.name}")  # Debug print
        
        # Check if doctor has availability set up
        has_availability = DoctorAvailability.objects.filter(doctor=doctor).exists()
        if not has_availability:
            print("No availability found for doctor")  # Debug print
            messages.warning(request, 'Please set up your availability schedule first.')
            return redirect('users:manage_availability')
        
        print("Doctor has availability")  # Debug print
        
        if request.method == 'POST':
            form = AppointmentForm(request.POST)
            # Remove doctor field validation temporarily
            form.fields['doctor'].required = False
            
            if form.is_valid():
                appointment = form.save(commit=False)
                # Explicitly set the doctor
                appointment.doctor = doctor
                appointment.status = 'scheduled'
                
                # Get form data
                appointment_date = form.cleaned_data['appointment_date']
                appointment_time = form.cleaned_data['appointment_time']
                
                print(f"Creating appointment for date: {appointment_date}, time: {appointment_time}")  # Debug print
                
                # Check if the selected time slot is available
                existing_appointment = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status='scheduled'
                ).exists()
                
                if existing_appointment:
                    messages.error(request, 'This time slot is already booked')
                else:
                    try:
                        appointment.save()
                        print(f"Appointment saved successfully: {appointment.id}")  # Debug print
                        messages.success(request, 'Appointment scheduled successfully')
                        return redirect('users:doctor_dashboard')
                    except Exception as save_error:
                        print(f"Error saving appointment: {str(save_error)}")  # Debug print
                        messages.error(request, f'Error saving appointment: {str(save_error)}')
            else:
                print("Form errors:", form.errors)  # Debug print
                messages.error(request, 'Please check the form data')
        else:
            # Pre-fill the doctor in the form
            form = AppointmentForm(initial={'doctor': doctor})
            form.fields['doctor'].initial = doctor
            form.fields['doctor'].widget.attrs['disabled'] = True
            
        context = {
            'form': form,
            'patients': Patient.objects.filter(clinic=doctor.clinic),
            'doctor_id': doctor.id,
            'doctor': doctor
        }
        return render(request, 'doctor/create_appointment.html', context)
        
    except Exception as e:
        print(f"Error in create_appointment: {str(e)}")  # Debug print
        messages.error(request, 'Error scheduling appointment')
        return redirect('users:doctor_dashboard')

@login_required
def doctor_dashboard(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        current_time = timezone.now().time()

        # Get today's appointments
        todays_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
            status='scheduled'
        ).order_by('appointment_time')  # Order by time

        # Get upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gt=today,
            status='scheduled'
        ).order_by('appointment_date', 'appointment_time')  # Order by date then time

        # Get monthly calendar data
        current_month = today.month
        current_year = today.year
        
        # Get all appointments for the current month
        month_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__year=current_year,
            appointment_date__month=current_month
        ).values('appointment_date').annotate(
            count=Count('id')
        )

        # Statistics
        total_patients_today = todays_appointments.count()
        completed_today = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
            status='completed'
        ).count()

        context = {
            'doctor': doctor,
            'todays_appointments': todays_appointments,
            'upcoming_appointments': upcoming_appointments,
            'total_patients_today': total_patients_today,
            'completed_today': completed_today,
            'current_month': today.strftime('%B %Y'),
        }
        
        return render(request, 'doctor/dashboard.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:login')
    except Exception as e:
        print(f"Error in doctor dashboard: {str(e)}")
        messages.error(request, 'Error accessing dashboard')
        return redirect('users:login')

@login_required
def appointment_detail(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        context = {
            'appointment': appointment,
            'patient': appointment.patient,
        }
        return render(request, 'doctor/appointment_detail.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Appointment.DoesNotExist:
        messages.error(request, 'Appointment not found')
        return redirect('users:doctor_appointments')

@login_required
def doctors_list(request):
    """View to list all doctors in a clinic"""
    try:
        clinic = request.user.userprofile.clinic
        doctors = Doctor.objects.filter(clinic=clinic).order_by('name')
        return render(request, 'clinic_admin/doctors_list.html', {
            'doctors': doctors
        })
    except Exception as e:
        messages.error(request, f"Error loading doctors: {str(e)}")
        return render(request, 'clinic_admin/doctors_list.html', {
            'doctors': []
        })
@login_required
def create_patient_doctor(request):
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
                    blood_group=request.POST.get('blood_group'),
                    phone_number=request.POST['phone_number'],
                    email=request.POST.get('email', ''),
                    address=request.POST.get('address', ''),
                    pincode=request.POST.get('pincode', ''),
                    clinic=clinic
                )
                messages.success(request, 'Patient added successfully!')
                return redirect('users:doctor_dashboard')
            except Exception as e:
                print(f"Error creating patient: {str(e)}")
                messages.error(request, f'Error adding patient: {str(e)}')
        
        # Create context with debug information
        context = {
            'blood_groups': Patient.BLOOD_GROUP_CHOICES,
            'gender_choices': Patient.GENDER_CHOICES,
            'debug_blood_groups': str(Patient.BLOOD_GROUP_CHOICES),  # Debug info
            'debug_gender': str(Patient.GENDER_CHOICES)              # Debug info
        }
        
       
        
        return render(request, 'doctor/create_patient.html', context)
    
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:doctor_dashboard')
    except Exception as e:
        print(f"Error in create_patient view: {str(e)}")
        messages.error(request, 'Error accessing patient creation')
        return redirect('users:doctor_dashboard')

@login_required
def create_appointment_doctor(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            appointment = Appointment.objects.create(
                patient_id=request.POST['patient'],
                doctor=doctor,
                appointment_date=request.POST['appointment_date'],
                appointment_time=request.POST['appointment_time'],
                symptoms=request.POST['symptoms'],
                existing_diseases=request.POST.get('existing_diseases', ''),
                current_medications=request.POST.get('current_medications', ''),
                notes=request.POST.get('notes', '')
            )
            messages.success(request, 'Appointment scheduled successfully')
            return redirect('users:doctor_dashboard')
            
        context = {
            'patients': Patient.objects.filter(clinic=doctor.clinic)
        }
        return render(request, 'doctor/create_appointment.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:doctor_dashboard')
    except Exception as e:
        print(f"Error creating appointment: {str(e)}")
        messages.error(request, 'Error scheduling appointment')
        return redirect('users:doctor_dashboard')

@login_required
def manage_availability(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            form = DoctorAvailabilityForm(request.POST)
            if form.is_valid():
                availability = form.save(commit=False)
                availability.doctor = doctor
                availability.save()
                messages.success(request, 'Availability schedule updated successfully')
                return redirect('users:doctor_dashboard')
        else:
            form = DoctorAvailabilityForm()
        
        availabilities = DoctorAvailability.objects.filter(doctor=doctor)
        context = {
            'form': form,
            'availabilities': availabilities
        }
        return render(request, 'doctor/manage_availability.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

@login_required
def generate_slots(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        end_date = today + timedelta(days=30)  # Generate slots for next 30 days
        
        # Get all leaves for the date range
        leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=end_date,
            end_date__gte=today
        )
        
        # Create a set of dates where doctor is on leave
        leave_dates = set()
        for leave in leaves:
            current_date = leave.start_date
            while current_date <= leave.end_date:
                leave_dates.add(current_date)
                current_date += timedelta(days=1)
        
        slots_created = 0
        dates_processed = 0
        
        current_date = today
        while current_date <= end_date:
            # Skip if doctor is on leave
            if current_date in leave_dates:
                current_date += timedelta(days=1)
                continue
                
            # Get availability for current day of week
            availabilities = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=current_date.weekday(),
                is_available=True
            )
            
            for availability in availabilities:
                slots = availability.generate_slots(current_date)
                
                for slot_time in slots:
                    # Create slot if it doesn't exist
                    slot, created = AppointmentSlot.objects.get_or_create(
                        doctor=doctor,
                        date=current_date,
                        start_time=slot_time.time(),
                        end_time=(slot_time + timedelta(minutes=10)).time()
                    )
                    if created:
                        slots_created += 1
            
            dates_processed += 1
            current_date += timedelta(days=1)
            
        messages.success(
            request, 
            f'Successfully generated {slots_created} slots across {dates_processed} days'
        )
        return redirect('users:manage_availability')
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        messages.error(request, f'Error generating slots: {str(e)}')
        return redirect('users:manage_availability')

@login_required
def manage_leaves(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason', '')
            
            try:
                leave = DoctorLeave.objects.create(
                    doctor=doctor,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )
                messages.success(request, 'Leave added successfully')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error adding leave: {str(e)}')
        
        # Get upcoming leaves
        upcoming_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            end_date__gte=timezone.now().date()
        ).order_by('start_date')
        
        context = {
            'upcoming_leaves': upcoming_leaves
        }
        return render(request, 'doctor/manage_leaves.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

@login_required
@user_is_doctor
def billing_overview(request):
    # Logic for doctor's billing overview
    total_appointments = Appointment.objects.filter(doctor=request.user.doctor).count()
    total_billing = Billing.objects.filter(appointment__doctor=request.user.doctor).aggregate(total=models.Sum('amount'))['total'] or 0

    context = {
        'total_appointments': total_appointments,
        'total_billing': total_billing,
    }
    return render(request, 'doctor/billing_overview.html', context)

@login_required
@user_is_doctor
def report_overview(request):
    # Logic for doctor's report overview
    context = {
        # Add report data here
    }
    return render(request, 'doctor/report_overview.html', context)

@login_required
def doctor_profile(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        if request.method == 'POST':
            # Handle profile updates here
            doctor.phone = request.POST.get('phone', doctor.phone)
            doctor.specialization = request.POST.get('specialization', doctor.specialization)
            doctor.save()
            messages.success(request, 'Profile updated successfully')
            return redirect('users:doctor_profile')
            
        context = {
            'doctor': doctor,
        }
        return render(request, 'doctor/profile.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

@login_required
def doctor_create_appointment(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        print(f"Doctor ID: {doctor.id}")  # Debug print
        
        if request.method == 'POST':
            print("POST data:", request.POST)  # Debug print
            form = AppointmentForm(request.POST)
            
            if form.is_valid():
                print("Form is valid")  # Debug print
                appointment = form.save(commit=False)
                appointment.status = 'scheduled'
                
                time_str = request.POST.get('appointment_time')
                if time_str:
                    appointment.appointment_time = datetime.strptime(time_str, '%H:%M').time()
                    appointment.save()
                    print(f"Appointment saved with doctor: {appointment.doctor.id}")  # Debug print
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:doctor_dashboard')
                else:
                    messages.error(request, 'Please select an appointment time.')
            else:
                print("Form errors:", form.errors)  # Debug print
                messages.error(request, 'Invalid form submission. Please check the data.')
        else:
            form = AppointmentForm(initial={'doctor': doctor})

        context = {
            'form': form,
            'doctor': doctor,
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'doctor/create_appointment.html', context)

    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in create_appointment: {str(e)}")
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('users:dashboard')

@login_required
def get_available_slots_doctor(request, doctor_id, date):
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        current_date = timezone.now().date()
        current_time = timezone.now().time()
        
        print(f"Generating slots for doctor: {doctor.name}, date: {date}")  # Debug print
        
        # Check if selected date is in the past
        if selected_date < current_date:
            return JsonResponse({
                'error': 'Cannot schedule appointments for past dates',
                'slots': []
            })
            
        # Get all booked appointments for the selected date
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status='scheduled'
        ).values_list('appointment_time', flat=True)
        
        # Generate time slots (9 AM to 5 PM, 30-minute intervals)
        available_slots = []
        slot_time = datetime.strptime('09:00', '%H:%M').time()
        end_time = datetime.strptime('17:00', '%H:%M').time()
        
        while slot_time <= end_time:
            # For current date, only show future time slots
            if selected_date == current_date and slot_time <= current_time:
                slot_time = (datetime.combine(datetime.today(), slot_time) + 
                           timedelta(minutes=30)).time()
                continue
                
            if slot_time not in booked_slots:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M')
                })
            
            # Update slot time
            slot_time = (datetime.combine(datetime.today(), slot_time) + 
                        timedelta(minutes=30)).time()
        
        print(f"Generated {len(available_slots)} available slots")  # Debug print
        
        return JsonResponse({
            'slots': available_slots,
            'doctor_name': doctor.name,
            'date': date
            
        })
        
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'slots': []
        }, status=400)

