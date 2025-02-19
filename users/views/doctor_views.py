from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Doctor, Appointment, Patient, DoctorAvailability, AppointmentSlot, DoctorLeave, Billing, Bill, Prescription, PatientVitals, PrescriptionItem, Drug
from ..serializers import DoctorSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from ..scripts.scrapeGpt01 import verify_doctor as verify_doctor_api
import json
from django.db.models import Q
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg
from ..forms import AppointmentForm, DoctorAvailabilityForm
from django.core.exceptions import ValidationError
from ..decorators import user_is_doctor
from django.db import models
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Case, When

def send_appointment_update_notification(appointment):
    try:
        subject = 'Appointment Update Notification'
        message = f"""
        Dear {appointment.patient.get_full_name()},

        Your appointment with Dr. {appointment.doctor.name} has been updated.

        New Details:
        Date: {appointment.appointment_date}
        Time: {appointment.appointment_time}
        
        If you have any questions, please contact the clinic.

        Best regards,
        {appointment.doctor.clinic.name}
        """
        
        print(f"Sending notification for appointment update to {appointment.patient.email}")
        return True
    except Exception as e:
        print(f"Error in notification: {str(e)}")
        return False

def send_status_update_notification(appointment):
    try:
        subject = 'Appointment Status Update'
        message = f"""
        Dear {appointment.patient.get_full_name()},

        Your appointment status has been updated to: {appointment.get_status_display()}

        Appointment Details:
        Date: {appointment.appointment_date}
        Time: {appointment.appointment_time}
        
        If you have any questions, please contact the clinic.

        Best regards,
        {appointment.doctor.clinic.name}
        """
        
        print(f"Sending status update notification to {appointment.patient.email}")
        return True
    except Exception as e:
        print(f"Error in status notification: {str(e)}")
        return False

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
        doctor = Doctor.objects.filter(user=request.user).first()
        
        if not doctor:
            messages.error(request, 'Doctor profile not found. Please complete your profile setup.')
            return redirect('users:doctor_profile')
        
        # Check if doctor has availability set up
        has_availability = DoctorAvailability.objects.filter(doctor=doctor).exists()
        if not has_availability:
            messages.warning(request, 'Please set up your availability schedule first.')
            return redirect('users:manage_availability')
        
        # Get patient_id from URL parameters
        patient_id = request.GET.get('patient')
        selected_patient = None
        if patient_id:
            try:
                selected_patient = Patient.objects.get(id=patient_id, clinic=doctor.clinic)
            except Patient.DoesNotExist:
                messages.warning(request, 'Selected patient not found')
        
        if request.method == 'POST':
            form = AppointmentForm(request.POST)
            form.fields['doctor'].required = False
            
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.doctor = doctor
                appointment.status = 'scheduled'
                
                appointment_date = form.cleaned_data['appointment_date']
                appointment_time = form.cleaned_data['appointment_time']
                
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
                        messages.success(request, 'Appointment scheduled successfully')
                        return redirect('users:doctor_dashboard')
                    except Exception as save_error:
                        messages.error(request, f'Error saving appointment: {str(save_error)}')
            else:
                messages.error(request, 'Please check the form data')
        else:
            # Pre-fill both doctor and patient if available
            initial_data = {'doctor': doctor}
            if selected_patient:
                initial_data['patient'] = selected_patient
            
            form = AppointmentForm(initial=initial_data)
            form.fields['doctor'].initial = doctor
            form.fields['doctor'].widget.attrs['disabled'] = True
            
            # If patient is pre-selected, disable the patient field
            if selected_patient:
                form.fields['patient'].initial = selected_patient
                form.fields['patient'].widget.attrs['disabled'] = True
        
        context = {
            'form': form,
            'patients': Patient.objects.filter(clinic=doctor.clinic),
            'doctor_id': doctor.id,
            'doctor': doctor,
            'selected_patient': selected_patient
        }
        return render(request, 'doctor/create_appointment.html', context)
        
    except Exception as e:
        messages.error(request, 'Error scheduling appointment')
        return redirect('users:doctor_dashboard')

@login_required
def doctor_dashboard(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        doctor_name = doctor.user_name
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


def appointment_detail_doctor(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        # Check if bill exists for this appointment
        bill = Bill.objects.filter(appointment=appointment).first()
        
        context = {
            'appointment': appointment,
            'patient': appointment.patient,
            'min_date': timezone.now().date(),
            'bill': bill  # Add bill to context
        }
        
        if request.headers.get('HX-Request'):
            return render(request, 'doctor/appointment_edit_modal.html', context)
        
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
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        
        print("Received data:", request.data)  # Debug print to see what we're getting
        
        # Map the incoming data to match Patient model fields
        patient_data = {
            'first_name': request.data.get('first_name'),
            'last_name': request.data.get('last_name'),
            'email': request.data.get('email', ''),
            'phone_number': request.data.get('phone', ''),  # Map 'phone' to 'phone_number'
            'gender': request.data.get('gender', 'M'),
            'address': request.data.get('address', ''),
            'clinic': clinic
        }
        
        # Create patient with mapped data
        patient = Patient.objects.create(**patient_data)
        
        return Response({
            'message': 'Patient added successfully!',
            'patient_id': patient.id
        }, status=status.HTTP_201_CREATED)
                
    except Exception as e:
        print(f"Error creating patient: {str(e)}")  # Debug print for error
        return Response({
            'error': f'Error adding patient: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

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
                    print("POST Data:", request.POST)
                    print("Appointment Date:", appointment_date_str)
                    print("Parsed Date:", appointment_date)
                    print("Stored Datetime:", stored_datetime, type(stored_datetime))
                    print("Comparison Result:", stored_datetime.date() == appointment_date)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_slots_doctor(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        date = request.GET.get('date')  # Get date from query params
        
        if not date:
            return Response({'error': 'Date parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        current_date = timezone.now().date()
        current_time = timezone.now().time()
        
        # Check if selected date is in the past
        if selected_date < current_date:
            return Response({
                'error': 'Cannot schedule appointments for past dates',
                'slots': []
            })
            
        # Get all booked appointments for the selected date
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status='scheduled'
        ).values_list('appointment_time', flat=True)
        
        # Get doctor's availability for this day
        availability = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=selected_date.weekday(),
            is_available=True
        ).first()
        
        if not availability:
            return Response({
                'slots': [],
                'message': 'Doctor not available on this day'
            })
        
        # Generate time slots based on doctor's availability
        available_slots = []
        slot_time = datetime.combine(selected_date, availability.start_time)
        end_time = datetime.combine(selected_date, availability.end_time)
        
        while slot_time.time() <= end_time.time():
            # For current date, only show future time slots
            if selected_date == current_date and slot_time.time() <= current_time:
                slot_time = slot_time + timedelta(minutes=30)
                continue
                
            if slot_time.time() not in booked_slots:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M')
                })
            
            slot_time = slot_time + timedelta(minutes=30)
        
        return Response({
            'slots': available_slots,
            'doctor_name': doctor.name,
            'date': date
        })
        
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@login_required
def update_appointment_status(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if request.method == 'POST':
            new_status = request.POST.get('status')
            if new_status in dict(Appointment.STATUS_CHOICES):
                appointment.status = new_status
                appointment.save()
                
                # If appointment is completed and no bill exists, redirect to create bill
                if new_status == 'completed' and not Bill.objects.filter(appointment=appointment).exists():
                    return JsonResponse({
                        'success': True,
                        'message': f'Appointment marked as {new_status}',
                        'redirect_url': reverse('users:create_bill', args=[appointment_id])
                    })
                
                return JsonResponse({
                    'success': True,
                    'message': f'Appointment marked as {new_status}'
                })
            return JsonResponse({
                'success': False,
                'message': 'Invalid status'
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def edit_appointment(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if request.method == 'POST':
            # Handle the form submission
            appointment.appointment_date = request.POST.get('appointment_date')
            appointment.appointment_time = request.POST.get('appointment_time')
            appointment.reason = request.POST.get('reason')
            appointment.save()
            
            # Send appointment update notification
            try:
                send_appointment_update_notification(appointment)
            except Exception as e:
                print(f"Error sending update notification: {str(e)}")
            
            messages.success(request, 'Appointment updated successfully')
            return redirect('users:doctor_appointments')
            
        context = {
            'appointment': appointment,
            'min_date': timezone.now().date(),
        }
        return render(request, 'doctor/appointment_edit_modal.html', context)
        
    except Exception as e:
        messages.error(request, f'Error updating appointment: {str(e)}')
        return redirect('users:doctor_appointments')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_create_appointment(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Parse the date and time from request data
        appointment_date = datetime.strptime(request.data['appointment_date'], '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.data['appointment_time'], '%H:%M').time()
        
        # Create appointment
        appointment = Appointment(
            doctor=doctor,
            patient_id=request.data['patient'],
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=request.data.get('reason', ''),
            status='scheduled'
        )
        
        # Manual validation
        if appointment_date < timezone.now().date():
            return Response({"error": "Cannot schedule appointments in the past"}, status=400)
            
        # Check for conflicts
        conflicts = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status='scheduled'
        )
        
        if conflicts.exists():
            return Response({"error": "This time slot is already booked"}, status=400)
            
        appointment.save()
        return Response({"message": "Appointment created successfully"}, status=201)
        
    except KeyError as e:
        return Response({"error": f"Missing required field: {str(e)}"}, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_patient_details(request, patient_id):
    try:
        # Get the requesting doctor
        doctor = Doctor.objects.get(user=request.user)
        
        # Get the patient and verify they belong to the doctor's clinic
        patient = get_object_or_404(Patient, id=patient_id, clinic=doctor.clinic)
        
        # Return patient details
        data = {
            'id': patient.id,
            'patient_id': f'PAT{str(patient.id).zfill(6)}',
            'first_name': patient.first_name,
            'last_name': patient.last_name,
            'gender': patient.gender,
            'phone_number': patient.phone_number,
            'email': patient.email,
            'address': patient.address,
            'pincode': patient.pincode,
            'blood_group': patient.blood_group,
            'allergies': patient.allergies,
            'clinic_id': patient.clinic.id
        }
        
        return Response(data, status=status.HTTP_200_OK)
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Patient.DoesNotExist:
        return Response({
            'error': 'Patient not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error fetching patient details: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_patient_prescriptions(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)
        
        if not Appointment.objects.filter(doctor=doctor, patient=patient).exists():
            return Response({'error': 'Unauthorized access'}, status=403)
        
        prescriptions = Prescription.objects.filter(patient=patient)
        data = [{
            'id': p.id,
            'medication': p.medication,
            'dosage': p.dosage,
            'duration': p.duration,
            'date_prescribed': p.created.strftime('%Y-%m-%d'),
            'notes': p.notes or ''
        } for p in prescriptions]
        return Response(data)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)
    except Exception as e:
        print(f"Error in prescriptions: {str(e)}")
        return Response({'error': 'Internal server error'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_patient_appointments(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)
        
        appointments = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).order_by('-appointment_date', '-appointment_time')
        
        data = [{
            'id': a.id,
            'appointment_date': a.appointment_date.strftime('%Y-%m-%d'),
            'appointment_time': a.appointment_time.strftime('%H:%M'),
            'status': a.status,
            'notes': a.reason or ''
        } for a in appointments]
        return Response(data)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)
    except Exception as e:
        print(f"Error in appointments: {str(e)}")  # Debug log
        return Response({'error': 'Internal server error'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_patient_medical_history(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)
        
        if not Appointment.objects.filter(doctor=doctor, patient=patient).exists():
            return Response({'error': 'Unauthorized access'}, status=403)
        
        history = MedicalHistory.objects.filter(patient=patient)
        data = [{
            'id': h.id,
            'condition': h.condition,
            'date': h.date.strftime('%Y-%m-%d') if h.date else None,
            'notes': h.notes or ''
        } for h in history]
        return Response(data)
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)
    except Exception as e:
        print(f"Error in medical history: {str(e)}")
        return Response({'error': 'Internal server error'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_details(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Calculate age from date_of_birth
        today = timezone.now().date()
        age = today.year - patient.date_of_birth.year - (
            (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
        )
        
        data = {
            'patient': {
                'id': patient.id,
                'first_name': patient.first_name,
                'last_name': patient.last_name,
                'email': patient.email,
                'phone_number': patient.phone_number,
                'date_of_birth': patient.date_of_birth.isoformat(),
                'age': age,
                'gender': patient.gender
            }
        }
        return Response(data)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except Exception as e:
        print(f"Error in get_patient_details: {str(e)}")
        return Response({'error': 'Internal server error'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_appointment_detail(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        data = {
            'id': appointment.id,
            'appointment_date': appointment.appointment_date,
            'appointment_time': appointment.appointment_time.strftime('%H:%M'),
            'status': appointment.status,
            'notes': appointment.reason or '',
            'patient_name': f"{appointment.patient.first_name} {appointment.patient.last_name}",
            'patient_id': appointment.patient.id,
        }
        
        return Response(data)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_prescription_api(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        data = request.data
        
        # Convert vital values to proper types
        def convert_to_decimal(value): 
            try:
                return float(value) if value and value.strip() else None
            except (ValueError, AttributeError):
                return None

        # Handle follow_up_date
        follow_up_date = data.get('follow_up_date')
        if follow_up_date and follow_up_date.strip():
            try:
                follow_up_date = datetime.strptime(follow_up_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid follow-up date format. Use YYYY-MM-DD'}, status=400)
        else:
            follow_up_date = None

        # Create patient vitals first
        vitals = PatientVitals.objects.create(
            patient_id=data['patient_id'],
            weight=convert_to_decimal(data.get('weight')),
            height=convert_to_decimal(data.get('height')),
            blood_pressure=data.get('blood_pressure'),
            temperature=convert_to_decimal(data.get('temperature')),
            heart_rate=convert_to_decimal(data.get('heart_rate')),
            oxygen_saturation=convert_to_decimal(data.get('oxygen_saturation')),
            recorded_by=request.user
        )

        # Create prescription
        prescription = Prescription.objects.create(
            patient_id=data['patient_id'],
            doctor=doctor,
            vitals=vitals,
            chief_complaints=data.get('chief_complaints'),
            clinical_findings=data.get('clinical_findings'),
            diagnosis=data.get('diagnosis'),
            advice=data.get('advice'),
            follow_up_date=follow_up_date
        )

        # Create prescription items
        medicines = data.get('medicines', [])
        for medicine in medicines:
            PrescriptionItem.objects.create(
                prescription=prescription,
                medicine=medicine['name'],
                dosage=medicine['dosage'],
                duration=medicine['duration'],
                duration_unit=medicine.get('duration_unit', 'days'),
                instructions=medicine.get('instructions', '')
            )

        return Response({
            'message': 'Prescription created successfully',
            'id': prescription.id
        }, status=201)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except ValueError as e:
        return Response({'error': f'Invalid value: {str(e)}'}, status=400)
    except Exception as e:
        print(f"Error creating prescription: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_latest_vitals(request, patient_id):
    try:
        # Get the most recent vitals for the patient
        latest_vitals = PatientVitals.objects.filter(
            patient_id=patient_id
        ).select_related('patient').order_by('-created_at').first()

        if latest_vitals:
            data = {
                'weight': str(latest_vitals.weight) if latest_vitals.weight else '',
                'height': str(latest_vitals.height) if latest_vitals.height else '',
                'blood_pressure': latest_vitals.blood_pressure or '',
                'temperature': str(latest_vitals.temperature) if latest_vitals.temperature else '',
                'heart_rate': str(latest_vitals.heart_rate) if latest_vitals.heart_rate else '',
                'oxygen_saturation': str(latest_vitals.oxygen_saturation) if latest_vitals.oxygen_saturation else '',
                'bmi': str(latest_vitals.bmi) if latest_vitals.bmi else '',
                'recorded_at': latest_vitals.created_at.strftime('%Y-%m-%d %H:%M'),
                'recorded_by': latest_vitals.recorded_by.get_full_name() if latest_vitals.recorded_by else 'Unknown'
            }
            return Response(data)
        return Response({
            'message': 'No previous vitals found'
        }, status=200)
        
    except Exception as e:
        print(f"Error fetching patient vitals: {str(e)}")
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_reports(request):
    try:
        period = request.GET.get('period', 'week')
        doctor = request.user.doctor
        today = timezone.now()

        # Set time period
        if period == 'week':
            start_date = today - timedelta(days=7)
            date_format = '%a'
        elif period == 'month':
            start_date = today - timedelta(days=30)
            date_format = '%d'
        else:  # year
            start_date = today - timedelta(days=365)
            date_format = '%b'

        # Get appointments in period
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=start_date,
            appointment_date__lte=today
        )

        # Get new patients in period
        new_patients = Patient.objects.filter(
            created_at__gte=start_date,
            created_at__lte=today,
            appointments__doctor=doctor
        ).distinct().count()

        # Get prescriptions in period
        prescriptions = Prescription.objects.filter(
            doctor=doctor,
            created_at__gte=start_date,
            created_at__lte=today
        )

        # Calculate appointment trend
        appointment_trend = appointments.extra(
            select={'date': f"DATE_FORMAT(appointment_date, '{date_format}')"}).\
            values('date').annotate(count=Count('id')).order_by('appointment_date')

        # Calculate completion rate
        completed = appointments.filter(status='COMPLETED').count()
        total = appointments.count()
        completion_rate = (completed / total * 100) if total > 0 else 0

        data = {
            'total_appointments': appointments.count(),
            'new_patients': new_patients,
            'total_prescriptions': prescriptions.count(),
            'revenue': calculate_revenue(appointments),  # Implement based on your billing logic
            'appointment_trend': {
                'labels': [item['date'] for item in appointment_trend],
                'data': [item['count'] for item in appointment_trend]
            },
            'avg_daily_appointments': round(appointments.count() / 7, 1),
            'completion_rate': round(completion_rate, 1),
            'patient_satisfaction': 95  # Implement based on your feedback system
        }

        return Response(data)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

def calculate_revenue(appointments):
    # Implement your revenue calculation logic here
    return sum(appointment.fee for appointment in appointments if appointment.fee)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_patient_api(request):
    try:
        # Get the doctor and their associated clinic
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        
        # Create patient with the data from request
        patient = Patient.objects.create(
            first_name=request.data.get('first_name'),
            last_name=request.data.get('last_name'),
            date_of_birth=request.data.get('date_of_birth'),  # You might want to convert age to date_of_birth
            gender=request.data.get('gender'),
            phone_number=request.data.get('phone_number'),
            email=request.data.get('email', ''),
            address=request.data.get('address', ''),
            existing_diseases=request.data.get('existing_diseases', ''),
            current_medications=request.data.get('current_medications', ''),
            allergies=request.data.get('allergies', ''),
            clinic=clinic,
            doctor=doctor
        )
        
        return Response({
            'message': 'Patient added successfully',
            'patient_id': patient.id
        }, status=status.HTTP_201_CREATED)
            
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error creating patient: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_slots_api(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Get schedule data from request
        schedule_data = request.data.get('schedule', {})
        unavailable_days = request.data.get('unavailable_days', [])
        
        # Delete existing availability for this doctor
        DoctorAvailability.objects.filter(doctor=doctor).delete()
        
        # Create new availability for each available day
        for day in range(7):
            if day not in unavailable_days:
                DoctorAvailability.objects.create(
                    doctor=doctor,
                    day_of_week=day,
                    start_time=schedule_data.get('start_time', '09:00'),
                    end_time=schedule_data.get('end_time', '17:00'),
                    is_available=True
                )
        
        # Generate slots for next 30 days
        today = timezone.now().date()
        end_date = today + timedelta(days=30)
        slots_created = 0
        dates_processed = 0
        
        current_date = today
        while current_date <= end_date:
            # Skip if day is marked as unavailable
            if current_date.weekday() in unavailable_days:
                current_date += timedelta(days=1)
                continue
            
            # Get availability for current day
            availability = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=current_date.weekday(),
                is_available=True
            ).first()
            
            if availability:
                # Delete existing slots for this date
                AppointmentSlot.objects.filter(
                    doctor=doctor,
                    date=current_date,
                    is_booked=False
                ).delete()
                
                # Convert times to datetime for calculations
                start_time = datetime.strptime(schedule_data.get('start_time', '09:00'), '%H:%M')
                end_time = datetime.strptime(schedule_data.get('end_time', '17:00'), '%H:%M')
                lunch_start = datetime.strptime(schedule_data.get('lunch_start', '13:00'), '%H:%M')
                lunch_end = datetime.strptime(schedule_data.get('lunch_end', '14:00'), '%H:%M')
                slot_duration = int(schedule_data.get('slot_duration', 30))
                
                current_time = start_time
                while current_time + timedelta(minutes=slot_duration) <= end_time:
                    # Skip lunch break
                    if not (lunch_start <= current_time < lunch_end):
                        try:
                            AppointmentSlot.objects.create(
                                doctor=doctor,
                                date=current_date,
                                start_time=current_time.time(),
                                end_time=(current_time + timedelta(minutes=slot_duration)).time(),
                                is_booked=False
                            )
                            slots_created += 1
                        except Exception as e:
                            print(f"Error creating slot: {str(e)}")
                    
                    current_time += timedelta(minutes=slot_duration)
                
                dates_processed += 1
            
            current_date += timedelta(days=1)
        
        return Response({
            'message': f'Successfully generated {slots_created} slots across {dates_processed} days',
            'slots_created': slots_created,
            'dates_processed': dates_processed
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_profile_api(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        data = {
            'id': doctor.id,
            'name': doctor.name,
            'email': doctor.email,
            'phone_number': doctor.phone_number,
            'specialization': doctor.specialization,
            'clinic': doctor.clinic.id
        }
        return Response(data, status=status.HTTP_200_OK)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_appointments_api(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        current_datetime = timezone.now()

        # Get all appointments for the doctor
        appointments = Appointment.objects.filter(
            doctor=doctor
        ).select_related('patient').order_by(
            # Future appointments first, then by date and time in descending order
            models.Case(
                When(appointment_date__gt=current_datetime.date(), then=0),
                When(appointment_date=current_datetime.date(), 
                     appointment_time__gt=current_datetime.time(), then=1),
                default=2
            ),
            '-appointment_date', 
            '-appointment_time'
        )

        appointments_data = []
        for appointment in appointments:
            appointments_data.append({
                'id': appointment.id,
                'patient_name': f"{appointment.patient.first_name} {appointment.patient.last_name}",
                'patient_id': appointment.patient.id,
                'date': appointment.appointment_date.strftime('%Y-%m-%d'),
                'time': appointment.appointment_time.strftime('%H:%M'),
                'status': appointment.status,
                'reason': appointment.reason or '',
                'is_future': (
                    appointment.appointment_date > current_datetime.date() or 
                    (appointment.appointment_date == current_datetime.date() and 
                     appointment.appointment_time > current_datetime.time())
                )
            })

        return Response({
            'appointments': appointments_data,
            'total_count': len(appointments_data)
        }, status=status.HTTP_200_OK)

    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error fetching appointments: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_prescriptions_api(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Get previous prescriptions
        prescriptions = Prescription.objects.filter(
            doctor=doctor,
            patient_id=patient_id
        ).select_related('patient').order_by('-date')
        
        prescriptions_data = []
        for prescription in prescriptions:
            # Use PrescriptionItem instead of PrescriptionMedicine
            medicines = PrescriptionItem.objects.filter(prescription=prescription)
            medicines_data = [{
                'name': med.medicine,
                'dosage': med.dosage,
                'duration': f"{med.duration} {med.duration_unit or ''}".strip(),
                'instructions': med.instructions
            } for med in medicines]
            
            prescriptions_data.append({
                'id': prescription.id,
                'created_at': prescription.date,
                'chief_complaints': prescription.chief_complaints,
                'clinical_findings': prescription.clinical_findings,
                'diagnosis': prescription.diagnosis,
                'advice': prescription.advice,
                'follow_up_date': prescription.follow_up_date,
                'medicines': medicines_data
            })
        
        return Response({
            'prescriptions': prescriptions_data
        }, status=status.HTTP_200_OK)
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error fetching prescriptions: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)