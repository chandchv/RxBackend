from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import DoctorAvailability, Patient, Doctor, Appointment, Prescription, PatientVitals, LabTest, LabTestPrescription
from notifications.models import Notification
from ..forms import AppointmentForm, PatientForm, AppointmentForm_patient, VitalsForm
from ..serializers import PatientSerializer
from django.contrib import messages
from ..models import Patient, UserProfile
from django.utils import timezone
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from notifications.utils import create_notification
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
import logging
from decimal import Decimal
from billing.models import Bill, BillItem, ConsultationBilling

logger = logging.getLogger(__name__)

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
        ).order_by('-created_at')
        
        # Get the latest patient vitals
        patient_vitals = PatientVitals.objects.filter(
            patient=patient
        ).order_by('-created_at').first()
        
        context = {
            'patient': patient,
            'appointments': appointments,
            'prescriptions': prescriptions,
            'doctor': doctor,
            'total_appointments': appointments.count(),
            'total_prescriptions': prescriptions.count(),
            'patient_vitals': patient_vitals,
        }
        
        return render(request, 'doctor/patient_detail.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found')
        return redirect('users:patients_list')

@login_required
def patient_vitals_history(request, patient_id):
    """View for displaying patient's historical vitals"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Get all vitals for this patient, ordered by most recent first
        vitals_history = PatientVitals.objects.filter(
            patient=patient
        ).order_by('-created_at')
        
        # Get the latest vitals for comparison
        latest_vitals = vitals_history.first()
        
        # Calculate trends (comparing with previous readings)
        vitals_with_trends = []
        for i, vitals in enumerate(vitals_history):
            trend_data = {}
            
            # Get previous reading for comparison
            if i < len(vitals_history) - 1:
                prev_vitals = vitals_history[i + 1]
                
                # Calculate trends for each vital
                if vitals.weight and prev_vitals.weight:
                    weight_diff = vitals.weight - prev_vitals.weight
                    trend_data['weight_trend'] = {
                        'change': weight_diff,
                        'direction': 'up' if weight_diff > 0 else 'down' if weight_diff < 0 else 'stable',
                        'percentage': round((weight_diff / prev_vitals.weight) * 100, 1) if prev_vitals.weight != 0 else 0
                    }
                
                if vitals.heart_rate and prev_vitals.heart_rate:
                    hr_diff = vitals.heart_rate - prev_vitals.heart_rate
                    trend_data['heart_rate_trend'] = {
                        'change': hr_diff,
                        'direction': 'up' if hr_diff > 0 else 'down' if hr_diff < 0 else 'stable'
                    }
                
                if vitals.temperature and prev_vitals.temperature:
                    temp_diff = vitals.temperature - prev_vitals.temperature
                    trend_data['temperature_trend'] = {
                        'change': temp_diff,
                        'direction': 'up' if temp_diff > 0 else 'down' if temp_diff < 0 else 'stable'
                    }
                
                if vitals.oxygen_saturation and prev_vitals.oxygen_saturation:
                    o2_diff = vitals.oxygen_saturation - prev_vitals.oxygen_saturation
                    trend_data['oxygen_trend'] = {
                        'change': o2_diff,
                        'direction': 'up' if o2_diff > 0 else 'down' if o2_diff < 0 else 'stable'
                    }
            
            vitals_with_trends.append({
                'vitals': vitals,
                'trends': trend_data
            })
        
        context = {
            'patient': patient,
            'vitals_history': vitals_with_trends,
            'latest_vitals': latest_vitals,
            'total_readings': vitals_history.count(),
        }
        
        return render(request, 'doctor/patient_vitals_history.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found')
        return redirect('users:patients_list')

@login_required
def add_patient_vitals(request, patient_id):
    """View for adding new patient vitals"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        if request.method == 'POST':
            form = VitalsForm(request.POST)
            if form.is_valid():
                vitals = form.save(commit=False)
                vitals.patient = patient
                vitals.recorded_by = request.user
                vitals.save()
                
                messages.success(request, 'Patient vitals recorded successfully!')
                return redirect('users:patient_vitals_history', patient_id=patient.id)
        else:
            form = VitalsForm()
        
        context = {
            'patient': patient,
            'form': form,
        }
        
        return render(request, 'doctor/add_patient_vitals.html', context)
        
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
                try:
                    # Create appointment without saving first
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
                        context = {
                            'form': form,
                            'patient': patient,
                            'doctors': Doctor.objects.filter(clinic=patient.clinic),
                            'min_date': timezone.now().date().isoformat(),
                        }
                        return render(request, 'patient/create_appointment.html', context)
                    
                    # Save the appointment
                    appointment.save()
                    
                    # --- BILLING: Create Bill and BillItem for consultation fee ---
                    if not hasattr(appointment, 'billing_bill'):
                        doctor = appointment.doctor
                        consultation_fee = getattr(doctor, 'consultation_fee', Decimal('500.00'))
                        bill = Bill.objects.create(
                            bill_type='consultation',
                            patient=patient,
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
                    
                    # Create notification for doctor
                    try:
                        create_notification(
                            user=appointment.doctor.user,
                            message=f"New appointment booked by {appointment.patient.get_full_name()} for {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}. Reason: {appointment.reason}",
                            notification_type='appointment_new'
                        )
                    except Exception as e:
                        logger.error(f"Error creating notification in patient_create_appointment: {e}")
                        messages.warning(request, "Appointment scheduled, but failed to send notification to doctor.")
                    
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('users:patient_dashboard')
                    
                except Exception as e:
                    logger.error(f"Error saving appointment: {e}")
                    messages.error(request, 'Failed to create appointment. Please try again.')
                    context = {
                        'form': form,
                        'patient': patient,
                        'doctors': Doctor.objects.filter(clinic=patient.clinic),
                        'min_date': timezone.now().date().isoformat(),
                    }
                    return render(request, 'patient/create_appointment.html', context)
            else:
                messages.error(request, 'Invalid form submission. Please check the data.')
                logger.error(f"Form errors: {form.errors}")
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
        logger.error(f"Error in patient_create_appointment: {e}")
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('users:dashboard')

@login_required
def patient_dashboard(request):
    try:
        patient = Patient.objects.get(user=request.user)
        
        # Get today's date at midnight for date comparison
        today = timezone.now().date()
        
        # Get upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__gte=today,
            status='scheduled'
        ).order_by('appointment_date', 'appointment_time')

        # Get previous appointments (including completed, cancelled, and missed)
        previous_appointments = Appointment.objects.filter(
            patient=patient
        ).filter(
            Q(appointment_date__lt=today) |
            Q(status__in=['completed', 'cancelled', 'missed', 'no_show'])
        ).order_by('-appointment_date', '-appointment_time')

        # Get recent prescriptions
        recent_prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-created_at')[:5]
        
        # Get completed lab tests
        completed_lab_tests = LabTest.objects.filter(
            prescription__patient=patient,
            status__in=['COMPLETED', 'REVIEWED']
        ).select_related('prescription', 'test_definition').order_by('-updated_at')[:5]
        
        # Get pending lab test prescriptions
        lab_prescriptions = LabTestPrescription.objects.filter(
            patient=patient
        ).order_by('-prescription_date')[:5]

        # Get recent notifications - Fixed: using recipient instead of user
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).order_by('-timestamp')[:10]

        context = {
            'patient': patient,
            'upcoming_appointments': upcoming_appointments,
            'previous_appointments': previous_appointments,
            'recent_prescriptions': recent_prescriptions,
            'total_appointments': upcoming_appointments.count(),
            'total_prescriptions': recent_prescriptions.count(),
            'completed_lab_tests': completed_lab_tests,
            'lab_prescriptions': lab_prescriptions,
            'notifications': notifications,
            'unread_notifications_count': notifications.count(),
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
        ).order_by('-created_at')
        
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

@login_required
def patient_test_results(request):
    """
    View for displaying all lab test results for a patient with pagination
    """
    if not hasattr(request.user, 'patient'):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('home')
    
    patient = request.user.patient
    
    # Get all lab tests for the patient - using the correct filtering
    # First get all lab test prescriptions for this patient
    lab_prescriptions = LabTestPrescription.objects.filter(patient=patient)
    
    # Then get all lab tests associated with these prescriptions
    lab_tests = []
    for prescription in lab_prescriptions:
        tests = LabTest.objects.filter(prescription=prescription)
        lab_tests.extend(tests)
    
    # Convert to a list for pagination
    lab_tests = sorted(lab_tests, key=lambda x: x.created_at, reverse=True)
    
    # Paginate the results
    paginator = Paginator(lab_tests, 10)  # Show 10 results per page
    page_number = request.GET.get('page', 1)
    
    try:
        paginated_tests = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        paginated_tests = paginator.page(1)
    
    context = {
        'lab_tests': paginated_tests,
        'patient': patient,
        'active_tab': 'test_results'
    }
    
    return render(request, 'patient/test_results.html', context)

@login_required
def patient_health_records(request):
    """View for listing all health records of a patient"""
    try:
        # Get the patient associated with the logged-in user
        patient = Patient.objects.get(user=request.user)
        
        # Get medical history and health records
        # In a real app, you might have a separate model for health records
        # For now, we'll just display some basic information
        
        # Get all prescriptions as health documents
        prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-date')
        
        # Get all lab tests
        lab_tests = LabTest.objects.filter(
            prescription__patient=patient
        ).select_related(
            'prescription',
            'test_definition'
        ).order_by('-updated_at')
        
        # Get all vitals records
        vitals = PatientVitals.objects.filter(
            patient=patient
        ).order_by('-created_at')
        
        context = {
            'patient': patient,
            'prescriptions': prescriptions,
            'lab_tests': lab_tests,
            'vitals': vitals,
        }
        
        return render(request, 'patient/health_records.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:login')
    except Exception as e:
        print(f"Error in patient_health_records: {str(e)}")
        messages.error(request, 'Error accessing health records')
        return redirect('users:patient_dashboard')

@login_required
def patient_appointments(request):
    """View for listing all appointments of a patient with search and filtering"""
    try:
        # Get the patient associated with the logged-in user
        patient = Patient.objects.get(user=request.user)
        
        # Get all appointments for this patient
        appointments = Appointment.objects.filter(
            patient=patient
        ).select_related('doctor').order_by('-appointment_date', '-appointment_time')
        
        # Filter options for status
        status_filter = request.GET.get('status', '')
        if status_filter:
            appointments = appointments.filter(status=status_filter)
        
        # Search functionality
        search_query = request.GET.get('search', '')
        if search_query:
            appointments = appointments.filter(
                Q(doctor__name__icontains=search_query) |
                Q(reason__icontains=search_query)
            )
        
        # Pagination
        paginator = Paginator(appointments, 10)  # Show 10 appointments per page
        page = request.GET.get('page')
        
        try:
            appointments = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page
            appointments = paginator.page(1)
        except EmptyPage:
            # If page is out of range, deliver last page of results
            appointments = paginator.page(paginator.num_pages)
        
        context = {
            'patient': patient,
            'appointments': appointments,
            'status_filter': status_filter,
            'search_query': search_query,
            'statuses': Appointment.STATUS_CHOICES,
        }
        
        return render(request, 'patient/appointments.html', context)          
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:login')
    except Exception as e:
        print(f"Error in patient_appointments: {str(e)}")
        messages.error(request, 'Error accessing appointments')
        return redirect('users:patient_dashboard')

@login_required
def patient_scheduling_dashboard(request):
    """Patient dashboard for scheduling system integration"""
    try:
        patient = Patient.objects.get(user=request.user)
        today = timezone.now().date()
        
        # Get appointments from both systems
        from scheduling.models import ScheduledAppointment
        
        # Legacy appointments (users app)
        legacy_appointments = Appointment.objects.filter(
            patient=patient,
            appointment_date__gte=today
        ).order_by('appointment_date', 'appointment_time')
        
        # Scheduling app appointments
        scheduled_appointments = ScheduledAppointment.objects.filter(
            patient=patient,
            appointment_date__gte=today
        ).order_by('appointment_date', 'appointment_time')
        
        # Combine all appointments
        all_appointments = []
        
        # Add legacy appointments
        for apt in legacy_appointments:
            all_appointments.append({
                'type': 'legacy',
                'appointment': apt,
                'doctor_name': apt.doctor.name,
                'date': apt.appointment_date,
                'time': apt.appointment_time,
                'status': apt.status,
                'reason': apt.reason or 'General Consultation'
            })
        
        # Add scheduled appointments
        for apt in scheduled_appointments:
            all_appointments.append({
                'type': 'scheduled',
                'appointment': apt,
                'doctor_name': apt.doctor.name,
                'date': apt.appointment_date,
                'time': apt.appointment_time,
                'status': apt.status,
                'reason': apt.reason or 'General Consultation'
            })
        
        # Sort by date and time
        all_appointments.sort(key=lambda x: (x['date'], x['time']))
        
        # Get upcoming appointments (next 7 days)
        week_from_now = today + timedelta(days=7)
        upcoming_appointments = [apt for apt in all_appointments if apt['date'] <= week_from_now]
        
        # Statistics
        total_upcoming = len(upcoming_appointments)
        total_all = len(all_appointments)
        
        context = {
            'patient': patient,
            'today': today,
            'all_appointments': all_appointments[:10],  # Show latest 10
            'upcoming_appointments': upcoming_appointments,
            'total_upcoming': total_upcoming,
            'total_all': total_all,
        }
        
        return render(request, 'patient/scheduling_dashboard.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('users:patient_profile')
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return redirect('users:patient_profile')

@login_required
def patient_book_appointment_scheduling(request):
    """Patient appointment booking using the scheduling system"""
    try:
        patient = Patient.objects.get(user=request.user)
        
        if request.method == 'POST':
            doctor_id = request.POST.get('doctor')
            appointment_date = request.POST.get('appointment_date')
            appointment_time = request.POST.get('appointment_time')
            reason = request.POST.get('reason', 'General Consultation')
            
            if doctor_id and appointment_date and appointment_time:
                doctor = Doctor.objects.get(id=doctor_id)
                
                # Create appointment in scheduling system
                from scheduling.models import ScheduledAppointment
                
                appointment = ScheduledAppointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    clinic=doctor.clinic,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reason=reason,
                    status='scheduled',
                    created_by=request.user
                )
                
                # Mark slot as booked if exists
                from users.models import AppointmentSlot
                slot = AppointmentSlot.objects.filter(
                    doctor=doctor,
                    date=appointment_date,
                    start_time=appointment_time,
                    is_booked=False
                ).first()
                
                if slot:
                    slot.is_booked = True
                    slot.save()
                
                messages.success(request, f'Appointment booked successfully with Dr. {doctor.name}!')
                return redirect('users:patient_scheduling_dashboard')
            else:
                messages.error(request, 'Please fill in all required fields.')
        
        # GET request - show booking form
        doctors = Doctor.objects.filter(is_active=True)
        
        context = {
            'patient': patient,
            'doctors': doctors,
            'min_date': timezone.now().date().isoformat(),
        }
        
        return render(request, 'patient/book_appointment_scheduling.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('users:patient_profile')
    except Exception as e:
        messages.error(request, f'Error booking appointment: {str(e)}')
        return redirect('users:patient_scheduling_dashboard')

