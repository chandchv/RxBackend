from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Doctor, Appointment, Patient, PatientVitals, DoctorAvailability, AppointmentSlot, DoctorLeave, Billing, Bill, Prescription, PrescriptionItem, Drug, PatientDoctor, ClinicHoliday
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
from django.db.models import Count, Avg, Sum
from ..forms import AppointmentForm, DoctorAvailabilityForm, DoctorLeaveForm
from django.core.exceptions import ValidationError, PermissionDenied
from ..decorators import user_is_doctor
from django.db import models
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Case, When
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from notifications.models import Notification
from notifications.utils import create_notification
from decimal import Decimal
from billing.models import BillItem, ConsultationBilling
from dateutil import parser

def send_appointment_create_notification(appointment):
    try:
        subject = 'New Appointment Scheduled'
        message = f"""
        Dear {appointment.patient.get_full_name()},

        Your appointment has been scheduled with Dr. {appointment.doctor.name}.

        Appointment Details:
        Date: {appointment.appointment_date}
        Time: {appointment.appointment_time}
        
        Please arrive 15 minutes before your scheduled time.
        If you need to reschedule or cancel, please contact the clinic.

        Best regards,
        {appointment.doctor.clinic.name}
        """
        
        # Send email notification if patient has email
        if appointment.patient.email:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [appointment.patient.email],
                fail_silently=False,
            )
        
        # Create in-app notification
        create_notification(
            recipient=appointment.patient.user,
            message=f"New appointment scheduled with Dr. {appointment.doctor.name} for {appointment.appointment_date} at {appointment.appointment_time}",
            sender=appointment.doctor.user,
            notification_type='appointment_created',
            action_url=f'/appointments/{appointment.id}/'
        )
        
        print(f"Appointment creation notification sent to {appointment.patient.email}")
        return True
    except Exception as e:
        print(f"Error in appointment creation notification: {str(e)}")
        return False

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
@user_is_doctor
def doctor_appointments(request):
    """View for doctor to see their appointments"""
    if not hasattr(request.user, 'doctor'):
        messages.error(request, 'Access denied. Doctor privileges required.')
        return redirect('users:dashboard')
    
    # Start with all appointments for this doctor
    appointments = Appointment.objects.filter(doctor=request.user.doctor)
    
    # Apply filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    patient_search = request.GET.get('patient_search')
    
    if date_from:
        appointments = appointments.filter(appointment_date__gte=date_from)
    
    if date_to:
        appointments = appointments.filter(appointment_date__lte=date_to)
    
    if status:
        appointments = appointments.filter(status=status)
    
    if patient_search:
        appointments = appointments.filter(
            Q(patient__first_name__icontains=patient_search) |
            Q(patient__last_name__icontains=patient_search) |
            Q(patient__user__first_name__icontains=patient_search) |
            Q(patient__user__last_name__icontains=patient_search)
        )
    
    # Order by date and time
    appointments = appointments.order_by('appointment_date', 'appointment_time')
    
    context = {
        'appointments': appointments,
        'today': timezone.now().date(),
    }
    
    return render(request, 'doctor/appointments.html', context)

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
                        
                        # Create scheduling bridge record with appointment types
                        from scheduling.models import ScheduledAppointment
                        ScheduledAppointment.objects.create(
                            appointment=appointment,
                            is_emergency=form.cleaned_data.get('is_emergency', False),
                            is_telemedicine=form.cleaned_data.get('is_telemedicine', False),
                            is_walk_in=form.cleaned_data.get('is_walk_in', False),
                            notes='',
                            created_by=request.user
                        )
                        
                        # --- BILLING: Create Bill and BillItem for consultation fee ---
                        consultation_fee = getattr(doctor, 'consultation_fee', Decimal('500.00'))
                        bill = Bill.objects.create(
                            bill_type='consultation',
                            patient=appointment.patient,
                            doctor=doctor,
                            clinic=doctor.clinic,
                            appointment=appointment,
                            bill_date=appointment.appointment_date,
                            due_date=appointment.appointment_date,
                            status='draft',
                            notes=f"Consultation with Dr. {doctor.name} on {appointment.appointment_date}"
                        )
                        BillItem.objects.create(
                            bill=bill,
                            item_name=f"Consultation with Dr. {doctor.name}",
                            description="Medical consultation",
                            quantity=1,
                            unit_price=consultation_fee
                        )
                        ConsultationBilling.objects.create(
                            appointment=appointment,
                            bill=bill,
                            doctor=doctor,
                            base_fee=consultation_fee,
                            final_fee=consultation_fee
                        )
                        bill.calculate_total()
                        bill.save()
                        
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
        excluded_statuses = ['cancelled', 'missed', 'no_show']

        # All appointments for today (scheduled + completed)
        todays_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today
        ).exclude(status__in=excluded_statuses).order_by('appointment_time')

        # Unique patients seen today
        todays_patients_count = todays_appointments.values('patient').distinct().count()

        # Completed appointments today
        completed_today = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
            status='completed'
        ).count()

        # Upcoming appointments (future dates only)
        upcoming_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gt=today
        ).exclude(status__in=excluded_statuses).order_by('appointment_date', 'appointment_time')
        upcoming_count = upcoming_appointments.count()

        # Pending appointments (all pending regardless of date)
        pending_count = Appointment.objects.filter(
            doctor=doctor,
            status='scheduled'
        ).count()

        # Appointments this month
        current_month = today.month
        current_year = today.year
        month_appointments_count = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__year=current_year,
            appointment_date__month=current_month
        ).exclude(status__in=excluded_statuses).count()

        # --- BILLING DATA ---
        from billing.models import Bill
        from django.db.models import Sum
        
        # Revenue this month
        first_day_of_month = today.replace(day=1)
        monthly_revenue = Bill.objects.filter(
            doctor=doctor,
            status='completed',
            bill_date__gte=first_day_of_month
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Draft bills count (use pending bills instead as there's no draft status)
        draft_bills_count = Bill.objects.filter(
            doctor=doctor,
            status='pending'
        ).count()
        
        # Pending bills count
        pending_bills_count = Bill.objects.filter(
            doctor=doctor,
            status='pending'
        ).count()
        
        # Bills paid today
        bills_paid_today = Bill.objects.filter(
            doctor=doctor,
            status='completed',
            updated_at__date=today
        ).count()

        context = {
            'doctor': doctor,
            'today': today,
            'todays_appointments': todays_appointments,
            'upcoming_appointments': upcoming_appointments[:5],  # Show only top 5 in dashboard
            'todays_patients_count': todays_patients_count,
            'completed_today': completed_today,
            'upcoming_count': upcoming_count,
            'pending_count': pending_count,
            'month_appointments_count': month_appointments_count,
            'current_month_label': today.strftime('%B %Y'),
            'monthly_revenue': monthly_revenue,
            'draft_bills_count': draft_bills_count,
            'pending_bills_count': pending_bills_count,
            'bills_paid_today': bills_paid_today,
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
            'bill': bill
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
@user_is_doctor
def create_patient_doctor(request):
    if request.method == 'POST':
        try:
            # Get data from form submission
            data = request.POST
            
            # Create user account for patient
            username = data.get('email') if data.get('email') else data.get('phone_number')
            # Generate a random password (12 characters with letters and digits)
            temp_password = get_random_string(12)
            
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=data.get('email'),
                password=temp_password,
                first_name=data.get('first_name'),
                last_name=data.get('last_name')
            )
            
            # Create patient
            patient = Patient.objects.create(
                user=user,  # Link the user account
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                email=data.get('email'),
                phone_number=data.get('phone_number'),
                date_of_birth=data.get('date_of_birth'),
                gender=data.get('gender', 'M'),  # Default to Male if not specified
                blood_group=data.get('blood_group', 'A+'),  # Default to A+ if not specified
                address=data.get('address'),
                pincode=data.get('pincode'),
                existing_diseases=data.get('existing_diseases'),
                current_medications=data.get('current_medications'),
                allergies=data.get('allergies'),
                clinic=request.user.doctor.clinic
            )
            
            # Create patient vitals
            PatientVitals.objects.create(
                patient=patient,
                weight=float(data.get('weight')) if data.get('weight') else None,
                height=float(data.get('height')) if data.get('height') else None,
                blood_pressure=data.get('blood_pressure'),
                temperature=float(data.get('temperature')) if data.get('temperature') else None,
                heart_rate=int(data.get('heart_rate')) if data.get('heart_rate') else None,
                oxygen_saturation=float(data.get('oxygen_saturation')) if data.get('oxygen_saturation') else None,
                recorded_by=request.user
            )
            
            # Create patient doctor relationship
            PatientDoctor.objects.create(
                patient=patient,
                doctor=request.user.doctor,
                is_primary=True
            )
            
            # Send notification to patient with their login credentials
            if patient.email:
                try:
                    create_notification(
                        recipient=user,
                        message=f"Your patient account has been created. Username: {username}, Temporary password: {temp_password}. Please change your password after logging in.",
                        sender=request.user,
                        notification_type='account_created',
                        action_url='/users/change_password/'
                    )
                except Exception as e:
                    print(f"Error sending notification: {str(e)}")
                    messages.warning(request, 'Patient created but failed to send login credentials notification.')
            
            messages.success(request, 'Patient created successfully')
            return redirect('users:patients_list')
                
        except Exception as e:
            print(f"Error creating patient: {str(e)}")
            messages.error(request, f'Error creating patient: {str(e)}')
            return redirect('users:create_patient_doctor')
    
    # GET request - show the form
    context = {
        'gender_choices': Patient.GENDER_CHOICES,
        'blood_group_choices': Patient.BLOOD_GROUP_CHOICES
    }
    return render(request, 'doctor/create_patient.html', context)

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
        
        # Define day choices
        DAY_OF_WEEK_CHOICES = [
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
            (6, 'Sunday')
        ]
        
        if request.method == 'POST':
            # Handle availability form submission
            if 'start_time' in request.POST:
                form = DoctorAvailabilityForm(request.POST)
                if form.is_valid():
                    # Get selected days from checkboxes
                    available_days = request.POST.getlist('available_days')
                    
                    if not available_days:
                        messages.error(request, 'Please select at least one day')
                        return redirect('users:manage_availability')
                    
                    # Get the start and end times from the form
                    start_time = form.cleaned_data['start_time']
                    end_time = form.cleaned_data['end_time']
                    
                    # First, make all days unavailable (to handle unchecked days)
                    # For existing days not in the selection, mark them as unavailable
                    for day in range(7):
                        if str(day) not in available_days:
                            availability = DoctorAvailability.objects.filter(
                                doctor=doctor,
                                day_of_week=day
                            ).first()
                            
                            if availability:
                                availability.is_available = False
                                availability.save()
                                print(f"Marked day {day} as unavailable")
                    
                    # Then, create or update availabilities for selected days
                    for day in available_days:
                        day_int = int(day)
                        
                        # Check if there are multiple availabilities for this day
                        existing_availabilities = DoctorAvailability.objects.filter(
                            doctor=doctor,
                            day_of_week=day_int
                        )
                        
                        # If multiple records exist, delete all but one
                        if existing_availabilities.count() > 1:
                            # Keep the first one and delete the rest
                            to_keep = existing_availabilities.first()
                            existing_availabilities.exclude(id=to_keep.id).delete()
                            print(f"Cleaned up duplicate availabilities for day {day_int}")
                        
                        # Update or create availability for this day
                        availability, created = DoctorAvailability.objects.update_or_create(
                            doctor=doctor,
                            day_of_week=day_int,
                            defaults={
                                'start_time': start_time,
                                'end_time': end_time,
                                'shift': 'morning',  # Set default shift
                                'is_available': True
                            }
                        )
                        
                        if created:
                            print(f"Created new availability for day {day_int}")
                        else:
                            print(f"Updated existing availability for day {day_int}")
                    
                    messages.success(request, 'Availability schedule saved successfully')
                    
                    # Make slot generation optional
                    if request.POST.get('auto_generate_slots') == 'on':
                        return redirect('users:generate_slots')
                    else:
                        return redirect('users:manage_availability')
                else:
                    # Form validation failed
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"Error in {field}: {error}")
                    return redirect('users:manage_availability')
            
            # Handle leave request submission
            elif 'start_date' in request.POST:
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                reason = request.POST.get('reason', '')
                leave_type = request.POST.get('leave_type', 'personal')
                
                try:
                    # Validate dates
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    # Check minimum notice period (at least 24 hours)
                    if start_date - timezone.now().date() < timedelta(days=1):
                        raise ValidationError('Leave must be requested at least 24 hours in advance')
                    
                    # Check maximum leave duration (30 days)
                    if (end_date - start_date).days > 30:
                        raise ValidationError('Maximum leave duration is 30 days')
                    
                    # Check for overlapping leaves
                    overlapping_leaves = DoctorLeave.objects.filter(
                        doctor=doctor,
                        start_date__lte=end_date,
                        end_date__gte=start_date,
                        status__in=['pending', 'approved']
                    )
                    
                    if overlapping_leaves.exists():
                        raise ValidationError('Leave request overlaps with existing approved or pending leaves')
                    
                    # Create leave request
                    leave = DoctorLeave.objects.create(
                        doctor=doctor,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason,
                        leave_type=leave_type,
                        status='pending'  # Default status
                    )
                    
                    # Notify admin for approval
                    admin_users = User.objects.filter(is_staff=True)
                    for admin in admin_users:
                        Notification.objects.create(
                            user=admin,
                            title='New Leave Request',
                            message=f'Doctor {doctor.user.get_full_name()} has requested leave from {start_date} to {end_date}',
                            notification_type='leave_request'
                        )
                    
                    messages.success(request, 'Leave request submitted successfully. Waiting for approval.')
                except ValidationError as e:
                    messages.error(request, str(e))
                except Exception as e:
                    messages.error(request, f'Error adding leave: {str(e)}')
                
                return redirect('users:manage_availability')
        else:
            form = DoctorAvailabilityForm()
        
        # Get current availability schedule
        availabilities = DoctorAvailability.objects.filter(doctor=doctor)
        
        # Get upcoming leaves
        upcoming_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            end_date__gte=timezone.now().date()
        ).order_by('start_date')
        
        # Get leave statistics
        total_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__year=timezone.now().year
        ).count()
        
        approved_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__year=timezone.now().year,
            status='approved'
        ).count()
        
        context = {
            'form': form,
            'availabilities': availabilities,
            'upcoming_leaves': upcoming_leaves,
            'total_leaves': total_leaves,
            'approved_leaves': approved_leaves,
            'leave_types': DoctorLeave.LEAVE_TYPE_CHOICES,
            'days': DAY_OF_WEEK_CHOICES,
            'today': timezone.now().date()
        }
        return render(request, 'doctor/manage_availability.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

@login_required
def generate_slots(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        today = timezone.now().date()
        
        # Get parameters from form if submitted
        if request.method == 'POST' and ('generate_slots_form' in request.POST or 'weekdays' in request.POST):
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            # Handle both comma-separated string and list
            weekdays_param = request.POST.get('weekdays', '')
            if weekdays_param:
                if ',' in weekdays_param:
                    selected_days = [int(day.strip()) for day in weekdays_param.split(',') if day.strip().isdigit()]
                else:
                    selected_days = request.POST.getlist('weekdays')
                    selected_days = [int(day) for day in selected_days if day.isdigit()]
            else:
                selected_days = request.POST.getlist('weekdays')
                selected_days = [int(day) for day in selected_days if day.isdigit()]
            
            # Convert to dates
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date = today
                
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end_date = today + timedelta(days=30)
                
            # Convert selected days to integers
            selected_weekdays = selected_days if selected_days else None
            
            print(f"Generating slots from {start_date} to {end_date} for weekdays: {selected_weekdays}")
        else:
            # Default values if not submitted
            start_date = today
            end_date = today + timedelta(days=30)
            selected_weekdays = None  # All available days
        
        # Log the start of slot generation
        print(f"Starting slot generation for doctor {doctor.name} (ID: {doctor.id})")
        
        # Get all leaves for the date range
        leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=end_date,
            end_date__gte=start_date,
            status='approved'  # Only consider approved leaves
        )
        
        # Get clinic holidays
        holidays = ClinicHoliday.objects.filter(
            clinic=clinic,
            date__gte=start_date,
            date__lte=end_date
        )
        
        # Create sets of dates where doctor is on leave or clinic is closed
        leave_dates = set()
        holiday_dates = set(holidays.values_list('date', flat=True))
        
        for leave in leaves:
            current_date = leave.start_date
            while current_date <= leave.end_date:
                leave_dates.add(current_date)
                current_date += timedelta(days=1)
        
        slots_created = 0
        dates_processed = 0
        slots_deleted = 0
        days_skipped = 0
        
        # Delete old slots that are in the past
        old_slots = AppointmentSlot.objects.filter(
            doctor=doctor,
            date__lt=today
        )
        slots_deleted = old_slots.count()
        old_slots.delete()
        
        # Check if doctor has any availability set up
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            is_available=True
        )
        
        if not availabilities.exists():
            messages.warning(request, 'No availability schedule found. Please set up your availability first.')
            return redirect('users:manage_availability')
        
        # Track which dates we've already processed to avoid duplicates
        processed_dates = set()
        
        # Safety counter to prevent infinite loops
        max_iterations = 100  # Increased for longer date ranges
        iteration_count = 0
        
        current_date = start_date
        while current_date <= end_date and iteration_count < max_iterations:
            iteration_count += 1
            print(f"Iteration {iteration_count}: Processing date {current_date}")
            
            # Skip if doctor is on leave or clinic is closed
            if current_date in leave_dates or current_date in holiday_dates:
                print(f"Skipping {current_date} - doctor on leave or clinic holiday")
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
                
            # Skip if we've already processed this date
            if current_date in processed_dates:
                print(f"Skipping {current_date} - already processed")
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
                
            # If specific weekdays are selected, check if current date's weekday is in the selection
            if selected_weekdays and current_date.weekday() not in selected_weekdays:
                print(f"Skipping {current_date} - weekday not selected")
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
            
            # Get availability for current day of week
            day_availabilities = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=current_date.weekday(),
                is_available=True
            )
            
            if not day_availabilities.exists():
                # No availability for this day of week
                print(f"Skipping {current_date} - no availability for this day of week")
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
            
            # Delete any existing slots for this date to avoid duplicates
            existing_slots = AppointmentSlot.objects.filter(
                doctor=doctor, 
                date=current_date,
                is_booked=False  # Only delete unbooked slots
            )
            if existing_slots.exists():
                slots_deleted += existing_slots.count()
                existing_slots.delete()
                print(f"Deleted {existing_slots.count()} existing slots for {current_date}")
            
            # Use only the first availability for this day to avoid duplicates
            # This is the key fix - we only use one availability record per day
            availability = day_availabilities.first()
            print(f"Generating slots for {current_date} from {availability.start_time} to {availability.end_time}")
            
            try:
                slots = availability.generate_slots(current_date)
                day_slots_created = 0
                
                for slot_time in slots:
                    # Create slot if it doesn't exist
                    slot, created = AppointmentSlot.objects.get_or_create(
                        doctor=doctor,
                        date=current_date,
                        start_time=slot_time.time(),
                        end_time=(slot_time + timedelta(minutes=10)).time(),
                        defaults={
                            'is_booked': False
                        }
                    )
                    if created:
                        day_slots_created += 1
                        slots_created += 1
                
                print(f"Created {day_slots_created} new slots for {current_date}")
            except Exception as slot_error:
                print(f"Error generating slot for {current_date}: {str(slot_error)}")
            
            # Mark this date as processed
            processed_dates.add(current_date)
            dates_processed += 1
            
            # IMPORTANT: Make sure we're properly incrementing the date
            prev_date = current_date
            current_date += timedelta(days=1)
            print(f"Incremented date from {prev_date} to {current_date}")
        
        # Check if we hit the safety limit
        if iteration_count >= max_iterations:
            print(f"WARNING: Reached maximum iteration count ({max_iterations}). Possible infinite loop detected.")
            messages.warning(
                request,
                f'Slot generation stopped after {iteration_count} iterations. Some slots may not have been created.'
            )
        
        # Log completion of slot generation
        print(f"Slot generation complete: {slots_created} slots created across {dates_processed} days ({days_skipped} days skipped)")
        
        if slots_created > 0:
            messages.success(
                request, 
                f'Successfully generated {slots_created} new slots and deleted {slots_deleted} old slots across {dates_processed} days. Your schedule is ready for appointments!'
            )
        else:
            messages.warning(
                request,
                f'No new slots were generated. Please check your availability schedule and try again.'
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
            leave_type = request.POST.get('leave_type', 'personal')
            
            try:
                # Validate dates
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                # Check minimum notice period (at least 24 hours)
                if start_date - timezone.now().date() < timedelta(days=1):
                    raise ValidationError('Leave must be requested at least 24 hours in advance')
                
                # Check maximum leave duration (30 days)
                if (end_date - start_date).days > 30:
                    raise ValidationError('Maximum leave duration is 30 days')
                
                # Check for overlapping leaves
                overlapping_leaves = DoctorLeave.objects.filter(
                    doctor=doctor,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    status__in=['pending', 'approved']
                )
                
                if overlapping_leaves.exists():
                    raise ValidationError('Leave request overlaps with existing approved or pending leaves')
                
                # Create leave request
                leave = DoctorLeave.objects.create(
                    doctor=doctor,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    leave_type=leave_type,
                    status='pending'  # Default status
                )
                
                # Notify admin for approval
                admin_users = User.objects.filter(is_staff=True)
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        title='New Leave Request',
                        message=f'Doctor {doctor.user.get_full_name()} has requested leave from {start_date} to {end_date}',
                        notification_type='leave_request'
                    )
                
                messages.success(request, 'Leave request submitted successfully. Waiting for approval.')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error adding leave: {str(e)}')
        
        # Get upcoming leaves
        upcoming_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            end_date__gte=timezone.now().date()
        ).order_by('start_date')
        
        # Get leave statistics
        total_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__year=timezone.now().year
        ).count()
        
        approved_leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__year=timezone.now().year,
            status='approved'
        ).count()
        
        pending_leaves = total_leaves - approved_leaves
        
        context = {
            'upcoming_leaves': upcoming_leaves,
            'total_leaves': total_leaves,
            'approved_leaves': approved_leaves,
            'pending_leaves': pending_leaves,
            'leave_types': DoctorLeave.LEAVE_TYPE_CHOICES,
            'today': timezone.now().date()
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
            return redirect('users/doctor/profile.html')
            
        context = {
            'doctor': doctor,
        }
        return render(request, 'users/doctor/profile.html', context)
        
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
                   
                    # Send appointment  create notification
                    try:
                        send_appointment_create_notification(appointment)
                    except Exception as e:
                        print(f"Error sending create notification: {str(e)}")
                    
                    messages.success(request, 'Appointment created successfully')
                    return redirect('users:doctor_appointments')
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
def get_available_slots_doctor(request, doctor_id, date):
    """
    View to get available slots for a specific doctor and date.
    Used in doctor's appointment creation views.
    """
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Check if the selected date is valid
        today = timezone.now().date()
        if selected_date < today:
            return JsonResponse({
                'error': 'Cannot view slots for past dates',
                'slots': []
            })
        
        # Get available slots from the AppointmentSlot model
        available_slots = AppointmentSlot.objects.filter(
            doctor=doctor,
            date=selected_date,
            is_booked=False
        ).order_by('start_time')
        
        # Format the slots for JSON response
        slots_data = []
        for slot in available_slots:
            slots_data.append({
                'id': slot.id,
                'time': slot.start_time.strftime('%H:%M'),
                'is_available': True
            })
        
        # Log for debugging
        print(f"Found {len(slots_data)} available slots for doctor {doctor_id} on {date}")
        
        return JsonResponse({
            'slots': slots_data,
            'doctor_name': doctor.name,
            'date': date
        })
        
    except Doctor.DoesNotExist:
        return JsonResponse({
            'error': 'Doctor not found',
            'slots': []
        }, status=404)
        
    except Exception as e:
        print(f"Error getting slots: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'slots': []
        }, status=400)

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
def api_patient_prescriptions(request, patient_id, prescription_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)
        prescription = Prescription.objects.get(id=prescription_id, patient=patient)
        if not Appointment.objects.filter(doctor=doctor, patient=patient, prescription=prescription).exists():
            return Response({'error': 'Unauthorized access'}, status=403)
        data = {
            'id': prescription.id,
            'patient_id': patient.id,
            'doctor_id': doctor.id,
            'prescription_date': prescription.created_at.strftime('%Y-%m-%d'),
            'prescription_items': []
        }
        prescriptions = PrescriptionItem.objects.filter(prescription=prescription)
        data = [{
            'id': p.id,
            'medication': p.medicine,
            'dosage': p.dosage,
            'duration': p.duration,
            'date_prescribed': p.created_at.strftime('%Y-%m-%d'),
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
        patient_vitals = PatientVitals.objects.filter(patient=patient).order_by('-created_at').first()

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
            },
            'patient_vitals': {}  # Initialize as an empty dictionary
        }

        # Only add patient_vitals data if patient_vitals is not None
        if patient_vitals:
            data['patient_vitals'] = {
                'weight': patient_vitals.weight,
                'height': patient_vitals.height,
                'blood_pressure': patient_vitals.blood_pressure,
                'temperature': patient_vitals.temperature,
                'heart_rate': patient_vitals.heart_rate,
                'oxygen_saturation': patient_vitals.oxygen_saturation,
                'bmi': patient_vitals.bmi,
                'recorded_at': patient_vitals.created_at.strftime('%Y-%m-%d %H:%M') if patient_vitals.created_at else None,
                'recorded_by': patient_vitals.recorded_by.get_full_name() if patient_vitals.recorded_by else 'Unknown'
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
            'id': str(appointment.id),  # Convert UUID to string
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
        
        # Create user account for patient
        username = request.data.get('email') if request.data.get('email') else request.data.get('phone_number')
        # Generate a random password (12 characters with letters and digits)
        temp_password = get_random_string(12)
        
        # Create user account
        user = User.objects.create_user(
            username=username,
            email=request.data.get('email'),
            password=temp_password,
            first_name=request.data.get('first_name'),
            last_name=request.data.get('last_name')
        )
        
        # Create patient with the data from request
        patient = Patient.objects.create(
            user=user,  # Link the user account
            first_name=request.data.get('first_name'),
            last_name=request.data.get('last_name'),
            date_of_birth=request.data.get('date_of_birth'),
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
        
        # Send notification to patient with their login credentials
        if patient.email:
            try:
                create_notification(
                    recipient=user,
                    message=f"Your patient account has been created. Username: {username}, Temporary password: {temp_password}. Please change your password after logging in.",
                    sender=request.user,
                    notification_type='account_created',
                    action_url='/users/change_password/'
                )
            except Exception as e:
                print(f"Error sending notification: {str(e)}")
        
        return Response({
            'message': 'Patient added successfully',
            'patient_id': patient.id,
            'username': username,
            'temp_password': temp_password  # Only return this in development
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
        
        # Get generation type - default to 'range' for backward compatibility
        generation_type = request.data.get('generation_type', 'range')
        
        if generation_type == 'week':
            # Week-based generation
            selected_date_str = request.data.get('selected_date')
            if not selected_date_str:
                return Response({
                    'error': 'selected_date is required for week generation'
                }, status=400)
            
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)
            
            # Calculate week start (Monday) and end (Sunday)
            week_start = selected_date - timedelta(days=selected_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Get selected weekdays (default to weekdays only)
            weekdays_data = request.data.get('weekdays', [0, 1, 2, 3, 4])  # Mon-Fri default
            if isinstance(weekdays_data, str):
                unavailable_days = [int(day.strip()) for day in weekdays_data.split(',') if day.strip().isdigit()]
            else:
                unavailable_days = weekdays_data
            
            # Get schedule data from request
            schedule_data = request.data.get('schedule', {})
            
            # Generate slots for the week using the week function
            return generate_week_slots_internal(doctor, week_start, week_end, schedule_data, unavailable_days)
        
        else:
            # Original range-based generation (30 days default)
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
            
            return generate_range_slots_internal(doctor, today, end_date, schedule_data, unavailable_days)
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor profile not found'
        }, status=404)
    except Exception as e:
        print(f"Error in generate_slots_api: {str(e)}")
        return Response({
            'error': str(e)
        }, status=500)

@login_required
def generate_slots_for_week(request):
    """Generate slots for a specific week based on selected date"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        
        if request.method == 'POST':
            selected_date_str = request.POST.get('selected_date')
            if not selected_date_str:
                messages.error(request, 'Please select a date for the week.')
                return redirect('users:manage_availability')
            
            # Parse the selected date
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid date format.')
                return redirect('users:manage_availability')
            
            # Calculate week start (Monday) and end (Sunday)
            week_start = selected_date - timedelta(days=selected_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Get selected weekdays from form
            weekdays_param = request.POST.get('weekdays', '')
            if weekdays_param:
                if ',' in weekdays_param:
                    selected_days = [int(day.strip()) for day in weekdays_param.split(',') if day.strip().isdigit()]
                else:
                    selected_days = request.POST.getlist('weekdays')
                    selected_days = [int(day) for day in selected_days if day.isdigit()]
            else:
                selected_days = [0, 1, 2, 3, 4]  # Default to weekdays
            
            print(f"Generating slots for week {week_start} to {week_end} for weekdays: {selected_days}")
            
            # Get all leaves for the week
            leaves = DoctorLeave.objects.filter(
                doctor=doctor,
                start_date__lte=week_end,
                end_date__gte=week_start,
                status='approved'
            )
            
            # Get clinic holidays for the week
            holidays = ClinicHoliday.objects.filter(
                clinic=clinic,
                date__gte=week_start,
                date__lte=week_end
            )
            
            # Create sets of dates where doctor is on leave or clinic is closed
            leave_dates = set()
            holiday_dates = set(holidays.values_list('date', flat=True))
            
            for leave in leaves:
                current_date = max(leave.start_date, week_start)
                end_date = min(leave.end_date, week_end)
                while current_date <= end_date:
                    leave_dates.add(current_date)
                    current_date += timedelta(days=1)
            
            # Check if doctor has availability set up
            availabilities = DoctorAvailability.objects.filter(
                doctor=doctor,
                is_available=True
            )
            
            if not availabilities.exists():
                messages.warning(request, 'No availability schedule found. Please set up your availability first.')
                return redirect('users:manage_availability')
            
            slots_created = 0
            dates_processed = 0
            days_skipped = 0
            
            # Process each day of the week
            current_date = week_start
            while current_date <= week_end:
                # Skip if doctor is on leave or clinic is closed
                if current_date in leave_dates or current_date in holiday_dates:
                    current_date += timedelta(days=1)
                    days_skipped += 1
                    continue
                
                # Check if this weekday is in selected days
                if current_date.weekday() not in selected_days:
                    current_date += timedelta(days=1)
                    days_skipped += 1
                    continue
                
                # Get availability for current day of week
                availability = availabilities.filter(
                    day_of_week=current_date.weekday(),
                    is_available=True
                ).first()
                
                if not availability:
                    current_date += timedelta(days=1)
                    days_skipped += 1
                    continue
                
                # Delete existing unbooked slots for this date
                existing_slots = AppointmentSlot.objects.filter(
                    doctor=doctor,
                    date=current_date,
                    is_booked=False
                )
                existing_slots.delete()
                
                # Generate new slots for this date
                try:
                    slots = availability.generate_slots(current_date)
                    day_slots_created = 0
                    
                    for slot_time in slots:
                        slot, created = AppointmentSlot.objects.get_or_create(
                            doctor=doctor,
                            date=current_date,
                            start_time=slot_time.time(),
                            end_time=(slot_time + timedelta(minutes=30)).time(),
                            defaults={'is_booked': False}
                        )
                        if created:
                            day_slots_created += 1
                            slots_created += 1
                    
                    dates_processed += 1
                    
                except Exception as slot_error:
                    print(f"Error generating slots for {current_date}: {str(slot_error)}")
                
                current_date += timedelta(days=1)
            
            if slots_created > 0:
                messages.success(
                    request, 
                    f'Successfully generated {slots_created} slots for the week of {week_start.strftime("%B %d, %Y")} across {dates_processed} days'
                )
            else:
                messages.warning(
                    request,
                    f'No new slots were generated for the selected week. Please check your availability schedule.'
                )
                
            return redirect('users:manage_availability')
        
        # GET request - redirect to availability management
        messages.info(request, 'Please use the availability page to generate slots.')
        return redirect('users:manage_availability')
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error generating week slots: {str(e)}")
        messages.error(request, f'Error generating slots: {str(e)}')
        return redirect('users:manage_availability')

def generate_week_slots_internal(doctor, week_start, week_end, schedule_data, unavailable_days):
    """Internal function to generate slots for a specific week"""
    try:
        # Get all leaves for the week
        leaves = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=week_end,
            end_date__gte=week_start,
            status='approved'
        )
        
        # Get clinic holidays for the week
        holidays = ClinicHoliday.objects.filter(
            clinic=doctor.clinic,
            date__gte=week_start,
            date__lte=week_end
        )
        
        # Create sets of dates where doctor is on leave or clinic is closed
        leave_dates = set()
        holiday_dates = set(holidays.values_list('date', flat=True))
        
        for leave in leaves:
            current_date = max(leave.start_date, week_start)
            end_date = min(leave.end_date, week_end)
            while current_date <= end_date:
                leave_dates.add(current_date)
                current_date += timedelta(days=1)
        
        # Check if doctor has availability set up
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            is_available=True
        )
        
        if not availabilities.exists():
            return Response({
                'error': 'No availability schedule found. Please set up your availability first.'
            }, status=400)
        
        slots_created = 0
        dates_processed = 0
        days_skipped = 0
        
        # Process each day of the week
        current_date = week_start
        while current_date <= week_end:
            # Skip if doctor is on leave or clinic is closed
            if current_date in leave_dates or current_date in holiday_dates:
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
            
            # Check if this weekday is in unavailable_days
            if current_date.weekday() in unavailable_days:
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
            
            # Get availability for current day of week
            availability = availabilities.filter(
                day_of_week=current_date.weekday(),
                is_available=True
            ).first()
            
            if not availability:
                current_date += timedelta(days=1)
                days_skipped += 1
                continue
            
            # Delete existing unbooked slots for this date
            existing_slots = AppointmentSlot.objects.filter(
                doctor=doctor,
                date=current_date,
                is_booked=False
            )
            existing_slots.delete()
            
            # Generate new slots for this date
            try:
                slots = availability.generate_slots(current_date)
                day_slots_created = 0
                
                for slot_time in slots:
                    slot, created = AppointmentSlot.objects.get_or_create(
                        doctor=doctor,
                        date=current_date,
                        start_time=slot_time.time(),
                        end_time=(slot_time + timedelta(minutes=30)).time(),
                        defaults={'is_booked': False}
                    )
                    if created:
                        day_slots_created += 1
                        slots_created += 1
                
                dates_processed += 1
                
            except Exception as slot_error:
                print(f"Error generating slots for {current_date}: {str(slot_error)}")
            
            current_date += timedelta(days=1)
        
        return Response({
            'message': f'Successfully generated {slots_created} slots for the week of {week_start.strftime("%B %d, %Y")} across {dates_processed} days',
            'slots_created': slots_created,
            'dates_processed': dates_processed,
            'days_skipped': days_skipped
        })
        
    except Exception as e:
        print(f"Error in generate_week_slots_internal: {str(e)}")
        return Response({
            'error': str(e)
        }, status=500)


def generate_range_slots_internal(doctor, start_date, end_date, schedule_data, unavailable_days):
    """Internal function to generate slots for a date range (original functionality)"""
    try:
        slots_created = 0
        dates_processed = 0
        
        current_date = start_date
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
        })
        
    except Exception as e:
        print(f"Error in generate_range_slots_internal: {str(e)}")
        return Response({
            'error': str(e)
        }, status=500)

@login_required
def doctor_calendar(request):
    """Calendar view for doctors to see their appointments"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        context = {
            'doctor': doctor,
        }
        return render(request, 'doctor/calendar.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Exception as e:
        print(f"Error in doctor calendar: {str(e)}")
        messages.error(request, 'Error loading calendar')
        return redirect('users:doctor_dashboard')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_calendar_events(request):
    """API endpoint to get calendar events for doctor"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Get appointments for the current month by default
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format'}, status=400)
        else:
            # Default to current month
            today = timezone.now().date()
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        )
        
        events = []
        for appointment in appointments:
            # Combine date and time for proper datetime
            appointment_datetime = datetime.combine(
                appointment.appointment_date, 
                appointment.appointment_time
            )
            
            events.append({
                'id': str(appointment.id),
                'title': f"{appointment.patient.get_full_name()} - {appointment.reason or 'Appointment'}",
                'start': appointment_datetime.isoformat(),
                'end': (appointment_datetime + timedelta(minutes=30)).isoformat(),
                'backgroundColor': {
                    'scheduled': '#3b82f6',
                    'completed': '#10b981',
                    'cancelled': '#ef4444',
                    'no_show': '#f59e0b'
                }.get(appointment.status, '#6b7280'),
                'borderColor': {
                    'scheduled': '#2563eb',
                    'completed': '#059669',
                    'cancelled': '#dc2626',
                    'no_show': '#d97706'
                }.get(appointment.status, '#4b5563'),
                'extendedProps': {
                    'patient_name': appointment.patient.get_full_name(),
                    'status': appointment.status,
                    'reason': appointment.reason,
                    'patient_phone': appointment.patient.phone_number
                }
            })
        
        return Response(events)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        print(f"Error in doctor calendar events: {str(e)}")
        return Response({'error': str(e)}, status=500)


@login_required
def request_leave(request):
    """Function for doctors to request leave"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason', '')
            leave_type = request.POST.get('leave_type', 'personal')
            
            try:
                # Validate dates
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                # Check minimum notice period (at least 24 hours)
                if start_date - timezone.now().date() < timedelta(days=1):
                    raise ValidationError('Leave must be requested at least 24 hours in advance')
                
                # Check maximum leave duration (30 days)
                if (end_date - start_date).days > 30:
                    raise ValidationError('Maximum leave duration is 30 days')
                
                # Check for overlapping leaves
                overlapping_leaves = DoctorLeave.objects.filter(
                    doctor=doctor,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    status__in=['pending', 'approved']
                )
                
                if overlapping_leaves.exists():
                    raise ValidationError('Leave request overlaps with existing approved or pending leaves')
                
                # Create leave request
                leave = DoctorLeave.objects.create(
                    doctor=doctor,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    leave_type=leave_type,
                    status='pending'  # Default status
                )
                
                messages.success(request, 'Leave request submitted successfully. Waiting for approval.')
                return redirect('users:manage_leaves')
                
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error adding leave: {str(e)}')
        
        # GET request - show form
        context = {
            'leave_types': DoctorLeave.LEAVE_TYPE_CHOICES,
            'today': timezone.now().date()
        }
        return render(request, 'doctor/request_leave.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_profile_api(request):
    """API endpoint to get doctor profile information"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        data = {
            'id': doctor.id,
            'name': doctor.name,
            'user_name': doctor.user_name,
            'email': doctor.user.email,
            'phone': getattr(doctor, 'phone', ''),
            'specialization': doctor.specialization,
            'license_number': doctor.license_number,
            'medical_council': doctor.medical_council,
            'verified': doctor.verified,
            'clinic_name': doctor.clinic.name if doctor.clinic else '',
            'created_at': doctor.created_at.isoformat() if hasattr(doctor, 'created_at') else None
        }
        
        return Response(data)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        print(f"Error in doctor profile API: {str(e)}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_appointments_api(request):
    """API endpoint to get doctor's appointments"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        # Get query parameters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        status_filter = request.GET.get('status')
        
        appointments = Appointment.objects.filter(doctor=doctor)
        
        # Apply filters
        if date_from:
            appointments = appointments.filter(appointment_date__gte=date_from)
        if date_to:
            appointments = appointments.filter(appointment_date__lte=date_to)
        if status_filter:
            appointments = appointments.filter(status=status_filter)
        
        appointments = appointments.order_by('appointment_date', 'appointment_time')
        
        data = []
        for appointment in appointments:
            data.append({
                'id': str(appointment.id),
                'patient_name': appointment.patient.get_full_name(),
                'patient_id': appointment.patient.id,
                'appointment_date': appointment.appointment_date.isoformat(),
                'appointment_time': appointment.appointment_time.strftime('%H:%M'),
                'status': appointment.status,
                'reason': appointment.reason or '',
                'patient_phone': appointment.patient.phone_number
            })
        
        return Response(data)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        print(f"Error in doctor appointments API: {str(e)}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_prescriptions_api(request, patient_id):
    """API endpoint to get prescriptions for a specific patient"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)
        
        # Verify doctor has access to this patient
        if not Appointment.objects.filter(doctor=doctor, patient=patient).exists():
            return Response({'error': 'Unauthorized access'}, status=403)
        
        prescriptions = Prescription.objects.filter(
            patient=patient,
            doctor=doctor
        ).order_by('-created_at')
        
        data = []
        for prescription in prescriptions:
            prescription_items = PrescriptionItem.objects.filter(prescription=prescription)
            
            data.append({
                'id': prescription.id,
                'date': prescription.created_at.strftime('%Y-%m-%d'),
                'chief_complaints': prescription.chief_complaints,
                'diagnosis': prescription.diagnosis,
                'advice': prescription.advice,
                'follow_up_date': prescription.follow_up_date.isoformat() if prescription.follow_up_date else None,
                'medicines': [
                    {
                        'medicine': item.medicine,
                        'dosage': item.dosage,
                        'duration': item.duration,
                        'instructions': item.instructions
                    } for item in prescription_items
                ]
            })
        
        return Response(data)
        
    except (Doctor.DoesNotExist, Patient.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)
    except Exception as e:
        print(f"Error in patient prescriptions API: {str(e)}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_slots_api(request):
    """API endpoint to get available appointment slots"""
    try:
        doctor_id = request.GET.get('doctor_id')
        date_str = request.GET.get('date')
        
        if not doctor_id or not date_str:
            return Response({'error': 'doctor_id and date are required'}, status=400)
        
        doctor = Doctor.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if the selected date is valid
        today = timezone.now().date()
        if selected_date < today:
            return Response({
                'error': 'Cannot view slots for past dates',
                'slots': []
            })
        
        # Get available slots from the AppointmentSlot model
        available_slots = AppointmentSlot.objects.filter(
            doctor=doctor,
            date=selected_date,
            is_booked=False
        ).order_by('start_time')
        
        # Format the slots for JSON response
        slots_data = []
        for slot in available_slots:
            slots_data.append({
                'id': slot.id,
                'time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
                'is_available': True
            })
        
        return Response({
            'slots': slots_data,
            'doctor_name': doctor.name,
            'date': date_str
        })
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor not found',
            'slots': []
        }, status=404)
        
    except Exception as e:
        print(f"Error getting available slots: {str(e)}")
        return Response({
            'error': str(e),
            'slots': []
        }, status=400)

@login_required
def generate_single_date_slots(request):
    """Generate slots for a single specific date with custom time settings"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        if request.method == 'POST':
            selected_date_str = request.POST.get('selected_date')
            start_time_str = request.POST.get('start_time', '09:00')
            end_time_str = request.POST.get('end_time', '17:00')
            lunch_start_str = request.POST.get('lunch_start', '13:00')
            lunch_end_str = request.POST.get('lunch_end', '14:00')
            slot_duration = int(request.POST.get('slot_duration', 30))
            
            if not selected_date_str:
                return JsonResponse({
                    'success': False,
                    'error': 'Please select a date.'
                })
            
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format.'
                })
            
            # Check if date is not in the past
            today = timezone.now().date()
            if selected_date < today:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot generate slots for past dates.'
                })
            
            # Parse times
            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                lunch_start = datetime.strptime(lunch_start_str, '%H:%M').time()
                lunch_end = datetime.strptime(lunch_end_str, '%H:%M').time()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid time format.'
                })
            
            # Validate times
            if start_time >= end_time:
                return JsonResponse({
                    'success': False,
                    'error': 'End time must be after start time.'
                })
            
            if lunch_start >= lunch_end:
                return JsonResponse({
                    'success': False,
                    'error': 'Lunch end time must be after lunch start time.'
                })
            
            # Check if doctor is on leave or clinic is closed
            leaves = DoctorLeave.objects.filter(
                doctor=doctor,
                start_date__lte=selected_date,
                end_date__gte=selected_date,
                status='approved'
            )
            
            if leaves.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Doctor is on approved leave on this date.'
                })
            
            # Check clinic holidays
            holidays = ClinicHoliday.objects.filter(
                clinic=doctor.clinic,
                date=selected_date
            )
            
            if holidays.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Clinic is closed on this date (holiday).'
                })
            
            # Delete existing unbooked slots for this date
            existing_slots = AppointmentSlot.objects.filter(
                doctor=doctor,
                date=selected_date,
                is_booked=False
            )
            slots_deleted = existing_slots.count()
            existing_slots.delete()
            
            # Generate new slots
            slots_created = 0
            current_time = datetime.combine(selected_date, start_time)
            end_datetime = datetime.combine(selected_date, end_time)
            lunch_start_datetime = datetime.combine(selected_date, lunch_start)
            lunch_end_datetime = datetime.combine(selected_date, lunch_end)
            
            while current_time + timedelta(minutes=slot_duration) <= end_datetime:
                # Skip lunch break
                if not (lunch_start_datetime <= current_time < lunch_end_datetime):
                    try:
                        slot, created = AppointmentSlot.objects.get_or_create(
                            doctor=doctor,
                            date=selected_date,
                            start_time=current_time.time(),
                            end_time=(current_time + timedelta(minutes=slot_duration)).time(),
                            defaults={'is_booked': False}
                        )
                        if created:
                            slots_created += 1
                    except Exception as e:
                        print(f"Error creating slot: {str(e)}")
                
                current_time += timedelta(minutes=slot_duration)
            
            return JsonResponse({
                'success': True,
                'message': f'Generated {slots_created} slots for {selected_date.strftime("%B %d, %Y")}',
                'slots_created': slots_created,
                'slots_deleted': slots_deleted,
                'date': selected_date_str
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Only POST method allowed.'
            })
            
    except Doctor.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Doctor profile not found.'
        })
    except Exception as e:
        print(f"Error in generate_single_date_slots: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_day_status(request, date):
    """Get the status of a specific day for the doctor (available/partial/full)"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get total available slots for this date
        total_slots = AppointmentSlot.objects.filter(
            doctor=doctor,
            date=selected_date
        ).count()
        
        # Get booked slots for this date
        booked_slots = AppointmentSlot.objects.filter(
            doctor=doctor,
            date=selected_date,
            is_booked=True
        ).count()
        
        # Also check appointments (in case slots weren't used)
        appointments_count = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status__in=['scheduled', 'completed']
        ).count()
        
        # Determine status
        if total_slots == 0 and appointments_count == 0:
            status = 'unavailable'
        elif booked_slots == 0 and appointments_count == 0:
            status = 'available'
        elif (booked_slots == total_slots) or (appointments_count > 0 and booked_slots + appointments_count >= total_slots):
            status = 'full'
        else:
            status = 'partial'
        
        return Response({
            'status': status,
            'total_slots': total_slots,
            'booked_slots': booked_slots,
            'appointments_count': appointments_count,
            'date': date
        })
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor not found'
        }, status=404)
    except Exception as e:
        print(f"Error getting day status: {str(e)}")
        return Response({
            'error': str(e)
        }, status=400)

@login_required
def integrated_scheduling_dashboard(request):
    """Integrated dashboard that combines both appointment systems"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        today = timezone.now().date()
        
        # Get appointments from both systems
        from scheduling.models import ScheduledAppointment, AppointmentSchedule
        
        # Check if doctor has scheduling availability set up
        has_scheduling_availability = AppointmentSchedule.objects.filter(
            doctor=doctor,
            is_active=True
        ).exists()
        
        # Legacy appointments (users app)
        legacy_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
            status__in=['scheduled', 'completed']
        ).order_by('appointment_time')
        
        # Scheduling app appointments
        scheduled_appointments = ScheduledAppointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
            status__in=['scheduled', 'confirmed', 'completed']
        ).order_by('appointment_time')
        
        # Combine and sort all appointments
        all_appointments = []
        
        # Add legacy appointments
        for apt in legacy_appointments:
            all_appointments.append({
                'type': 'legacy',
                'appointment': apt,
                'patient_name': apt.patient.get_full_name(),
                'time': apt.appointment_time,
                'status': apt.status,
                'reason': apt.reason or 'General Consultation'
            })
        
        # Add scheduled appointments
        for apt in scheduled_appointments:
            all_appointments.append({
                'type': 'scheduled',
                'appointment': apt,
                'patient_name': apt.patient.get_full_name(),
                'time': apt.appointment_time,
                'status': apt.status,
                'reason': apt.reason or 'General Consultation'
            })
        
        # Sort by time
        all_appointments.sort(key=lambda x: x['time'])
        
        # Statistics
        total_today = len(all_appointments)
        completed_today = len([a for a in all_appointments if a['status'] in ['completed']])
        scheduled_today = len([a for a in all_appointments if a['status'] in ['scheduled', 'confirmed']])
        
        # Additional counts for the stats cards
        today_appointments_count = total_today
        upcoming_appointments_count = (
            Appointment.objects.filter(
                doctor=doctor,
                appointment_date__gt=today,
                status__in=['scheduled']
            ).count() +
            ScheduledAppointment.objects.filter(
                doctor=doctor,
                appointment_date__gt=today,
                status__in=['scheduled', 'confirmed']
            ).count()
        )
        completed_today_count = completed_today
        
        context = {
            'doctor': doctor,
            'today': today,
            'all_appointments': all_appointments,
            'total_today': total_today,
            'completed_today': completed_today,
            'scheduled_today': scheduled_today,
            'today_appointments_count': today_appointments_count,
            'upcoming_appointments_count': upcoming_appointments_count,
            'completed_today_count': completed_today_count,
            'has_scheduling_availability': has_scheduling_availability,
        }
        
        return render(request, 'doctor/integrated_scheduling_dashboard.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('users:doctor_profile')
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return redirect('users:doctor_profile')

@login_required
def sync_appointments_to_scheduling(request):
    """Sync existing appointments to the scheduling app"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        from scheduling.models import ScheduledAppointment
        
        if request.method == 'POST':
            # Get all appointments that haven't been synced yet
            legacy_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date__gte=timezone.now().date()
            ).exclude(
                id__in=ScheduledAppointment.objects.filter(
                    doctor=doctor
                ).values_list('id', flat=True)
            )
            
            synced_count = 0
            for apt in legacy_appointments:
                # Create corresponding ScheduledAppointment
                scheduled_apt = ScheduledAppointment.objects.create(
                    patient=apt.patient,
                    doctor=apt.doctor,
                    clinic=apt.doctor.clinic,
                    appointment_date=apt.appointment_date,
                    appointment_time=apt.appointment_time,
                    reason=apt.reason or 'General Consultation',
                    status='scheduled' if apt.status == 'scheduled' else 'completed',
                    created_by=request.user,
                    notes=f'Synced from legacy appointment #{apt.id}'
                )
                synced_count += 1
            
            messages.success(request, f'Successfully synced {synced_count} appointments to the scheduling system.')
            return JsonResponse({'success': True, 'synced_count': synced_count})
        
        # GET request - show sync options
        legacy_count = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=timezone.now().date()
        ).count()
        
        scheduled_count = ScheduledAppointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=timezone.now().date()
        ).count()
        
        context = {
            'doctor': doctor,
            'legacy_count': legacy_count,
            'scheduled_count': scheduled_count,
        }
        
        return render(request, 'doctor/sync_appointments.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('users:doctor_profile')
    except Exception as e:
        messages.error(request, f'Error syncing appointments: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_is_doctor
def doctor_create_billing(request):
    """Create billing for doctor's consultations and services"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
        
        # Get completed appointments that don't have bills yet
        completed_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='completed'
        ).exclude(
            billing_bill__isnull=False
        ).select_related('patient').order_by('-appointment_date')
        
        # Get patients for creating bills without appointments
        patients = Patient.objects.filter(clinic=clinic).order_by('first_name')
        
        if request.method == 'POST':
            # Get form data
            patient_id = request.POST.get('patient')
            appointment_id = request.POST.get('appointment')
            bill_type = request.POST.get('bill_type', 'consultation')
            notes = request.POST.get('notes', '')
            
            # Get bill items data
            item_names = request.POST.getlist('item_name[]')
            item_descriptions = request.POST.getlist('item_description[]')
            item_quantities = request.POST.getlist('item_quantity[]')
            item_prices = request.POST.getlist('item_price[]')
            
            # Validate required fields
            if not patient_id:
                messages.error(request, 'Please select a patient.')
                return redirect('users:doctor_create_billing')
            
            if not item_names or not any(item_names):
                messages.error(request, 'Please add at least one bill item.')
                return redirect('users:doctor_create_billing')
            
            # Get patient
            patient = get_object_or_404(Patient, id=patient_id, clinic=clinic)
            
            # Get appointment if specified
            appointment = None
            if appointment_id:
                appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
            
            # Create the bill
            bill = Bill.objects.create(
                patient=patient,
                doctor=doctor,
                clinic=clinic,
                appointment=appointment,
                bill_type=bill_type,
                bill_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=30),
                status='draft',
                notes=notes
            )
            
            # Create bill items
            for i, item_name in enumerate(item_names):
                if item_name and i < len(item_quantities) and i < len(item_prices):
                    try:
                        quantity = int(item_quantities[i]) if item_quantities[i] else 1
                        price = Decimal(item_prices[i]) if item_prices[i] else Decimal('0.00')
                        description = item_descriptions[i] if i < len(item_descriptions) else ''
                        
                        BillItem.objects.create(
                            bill=bill,
                            item_name=item_name,
                            description=description,
                            quantity=quantity,
                            unit_price=price
                        )
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error processing bill item {i}: {e}")
                        continue
            
            # Recalculate bill total
            bill.calculate_total()
            bill.save()
            
            # If this is for a completed appointment, create consultation billing
            if appointment and bill_type == 'consultation':
                ConsultationBilling.objects.create(
                    appointment=appointment,
                    bill=bill,
                    doctor=doctor,
                    base_fee=bill.total,
                    final_fee=bill.total
                )
            
            messages.success(request, f'Bill #{bill.bill_number} created successfully!')
            return redirect('users:doctor_billing_detail', billing_id=bill.id)
        
        context = {
            'doctor': doctor,
            'clinic': clinic,
            'completed_appointments': completed_appointments,
            'patients': patients,
        }
        
        return render(request, 'doctor/create_billing.html', context)
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('users:doctor_dashboard')
    except Exception as e:
        messages.error(request, f'Error creating bill: {str(e)}')
        return redirect('users:doctor_dashboard')

@login_required
@user_is_doctor
def doctor_billing_detail(request, billing_id):
    """View billing details for doctor"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        
        bill = get_object_or_404(Bill, id=billing_id, doctor=doctor)
        
        context = {
            'bill': bill,
            'doctor': doctor,
            'clinic': doctor.clinic
        }
        
        return render(request, 'doctor/billing_detail.html', context)
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('users:doctor_dashboard')
    except Exception as e:
        messages.error(request, f'Error viewing billing: {str(e)}')
        return redirect('users:doctor_dashboard')

@login_required
@user_is_doctor
def attend_appointment(request, appointment_id):
    """Mark appointment as in progress when doctor starts attending"""
    try:
        doctor = request.user.doctor
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if appointment.status != 'scheduled':
            messages.error(request, 'Only scheduled appointments can be attended.')
            return redirect('users:doctor_dashboard')
        
        appointment.status = 'in_progress'
        appointment.save()
        
        messages.success(request, f'Started attending {appointment.patient.get_full_name()}')
        
        # Redirect to patient detail or consultation page
        return redirect('users:patient_detail', patient_id=appointment.patient.id)
        
    except Exception as e:
        messages.error(request, f'Error updating appointment: {str(e)}')
        return redirect('users:doctor_dashboard')


@login_required
@user_is_doctor
def postpone_appointment(request, appointment_id):
    """Handle postponing an appointment to a future date"""
    try:
        doctor = request.user.doctor
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if request.method == 'POST':
            new_date = request.POST.get('new_date')
            new_time = request.POST.get('new_time')
            reason = request.POST.get('reason', '')
            
            if not new_date or not new_time:
                messages.error(request, 'Please provide both new date and time.')
                return redirect('users:doctor_dashboard')
            
            # Update appointment
            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.reason = f"{appointment.reason}\nPostponed: {reason}" if appointment.reason else f"Postponed: {reason}"
            appointment.save()
            
            # Send notification to patient
            try:
                create_notification(
                    recipient=appointment.patient.user,
                    message=f"Your appointment has been postponed to {new_date} at {new_time}. Reason: {reason}",
                    sender=request.user,
                    notification_type='appointment_postponed',
                    action_url=f'/appointments/{appointment.id}/'
                )
            except:
                pass  # Don't fail if notification fails
            
            messages.success(request, f'Appointment postponed to {new_date} at {new_time}')
            return redirect('users:doctor_dashboard')
        
        # GET request - show postpone form
        context = {
            'appointment': appointment,
            'min_date': timezone.now().date() + timezone.timedelta(days=1),  # Tomorrow onwards
        }
        return render(request, 'doctor/postpone_appointment.html', context)
        
    except Exception as e:
        messages.error(request, f'Error postponing appointment: {str(e)}')
        return redirect('users:doctor_dashboard')


@login_required
@user_is_doctor
def complete_appointment(request, appointment_id):
    """Mark appointment as completed after consultation"""
    try:
        doctor = request.user.doctor
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if appointment.status not in ['scheduled', 'in_progress']:
            messages.error(request, 'This appointment cannot be completed.')
            return redirect('users:doctor_dashboard')
        
        appointment.status = 'completed'
        appointment.save()
        
        messages.success(request, f'Appointment with {appointment.patient.get_full_name()} completed')
        return redirect('users:doctor_dashboard')
        
    except Exception as e:
        messages.error(request, f'Error completing appointment: {str(e)}')
        return redirect('users:doctor_dashboard')


@login_required
@user_is_doctor  
def appointment_actions(request, appointment_id):
    """Handle AJAX requests for appointment actions"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        doctor = request.user.doctor
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        action = request.POST.get('action')
        
        if action == 'attend':
            if appointment.status != 'scheduled':
                return JsonResponse({'success': False, 'error': 'Only scheduled appointments can be attended.'})
            
            appointment.status = 'in_progress'
            appointment.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Started attending {appointment.patient.get_full_name()}',
                'new_status': 'in_progress',
                'new_status_display': 'In Progress'
            })
        
        elif action == 'complete':
            if appointment.status not in ['scheduled', 'in_progress']:
                return JsonResponse({'success': False, 'error': 'This appointment cannot be completed.'})
            
            appointment.status = 'completed'
            appointment.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Appointment with {appointment.patient.get_full_name()} completed',
                'new_status': 'completed',
                'new_status_display': 'Completed'
            })
        
        elif action == 'no_show':
            if appointment.status != 'scheduled':
                return JsonResponse({'success': False, 'error': 'Only scheduled appointments can be marked as no-show.'})
            
            appointment.status = 'no_show'
            appointment.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Marked {appointment.patient.get_full_name()} as no-show',
                'new_status': 'no_show',
                'new_status_display': 'No Show'
            })
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_dashboard_calendar_events(request):
    """API endpoint to get appointments and available slots for the doctor dashboard calendar"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        appointments = Appointment.objects.filter(doctor=doctor)
        
        if start_date:
            # Parse the ISO date string and extract just the date part
            try:
                parsed_date = parser.parse(start_date).date()
                appointments = appointments.filter(appointment_date__gte=parsed_date)
            except Exception as e:
                print(f"Error parsing start date: {e}")
        
        if end_date:
            # Parse the ISO date string and extract just the date part
            try:
                parsed_date = parser.parse(end_date).date()
                appointments = appointments.filter(appointment_date__lte=parsed_date)
            except Exception as e:
                print(f"Error parsing end date: {e}")
        
        events = []
        for appointment in appointments:
            # Different colors for different statuses
            color_map = {
                'scheduled': '#3788d8',
                'in_progress': '#ffc107',
                'completed': '#28a745',
                'cancelled': '#dc3545',
                'no_show': '#fd7e14',
                'missed': '#17a2b8',
            }
            
            # Create the appointment datetime
            start_datetime = datetime.combine(
                appointment.appointment_date,
                appointment.appointment_time
            )
            
            # Assume appointments last 30 minutes
            end_datetime = start_datetime + timedelta(minutes=30)
            
            events.append({
                'id': appointment.id,
                'title': f"{appointment.patient.get_full_name()}",
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'color': color_map.get(appointment.status, '#3788d8'),
                'extendedProps': {
                    'patient': appointment.patient.get_full_name(),
                    'doctor': appointment.doctor.name,
                    'status': appointment.get_status_display(),
                    'reason': appointment.reason or 'No reason provided',
                    'appointment_id': appointment.id,
                    'patient_id': appointment.patient.id,
                    'phone': appointment.patient.phone_number,
                    'type': 'appointment'
                },
                'url': f'/users/patient/{appointment.patient.id}/',
            })
        
        return Response(events, status=status.HTTP_200_OK)
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
