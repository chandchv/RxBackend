from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from ..forms import StaffAppointmentForm, BillForm, BillItemForm
from ..models import Appointment, Patient, Prescription, LabTest, Billing, Doctor, PatientVitals, StaffLeave, DoctorAvailability
from notifications.models import Notification
from ..serializers import AppointmentSerializer, PatientSerializer, PrescriptionSerializer, LabTestSerializer, BillingSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .permissions import IsStaff
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
import logging
from notifications.utils import create_notification
from django.http import JsonResponse

logger = logging.getLogger(__name__)
User = get_user_model()

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
@user_is_staff
def staff_create_appointment(request):
    """Create new appointment for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic

        # Get available patients and doctors for the clinic
        patients = Patient.objects.filter(clinic=clinic)
        doctors = Doctor.objects.filter(clinic=clinic)
        
        if request.method == 'POST':
            try:
                # Get form data
                patient_id = request.POST.get('patient')
                doctor_id = request.POST.get('doctor')
                appointment_date = request.POST.get('appointment_date')
                appointment_time = request.POST.get('appointment_time')
                reason = request.POST.get('reason')
                
                # Validate required fields
                if not all([patient_id, doctor_id, appointment_date, appointment_time, reason]):
                    messages.error(request, 'Please fill in all required fields.')
                    return redirect('users:staff_create_appointment')
                
                # Get patient and doctor objects
                patient = get_object_or_404(Patient, id=patient_id, clinic=clinic)
                doctor = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
                
                # Create appointment
                appointment = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reason=reason,
                    status='scheduled'
                )
                
                # --- Add Notifications --- 
                notification_success = True
                try:
                    # Check if doctor has a user account
                    if hasattr(doctor, 'user') and doctor.user:
                        # Notify Doctor
                        doctor_notification = create_notification(
                            recipient=doctor.user,
                            message=f"New appointment scheduled by staff for {patient.get_full_name()} on {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}.",
                            sender=request.user, 
                            notification_type='appointment_new',
                            related_object=appointment
                        )
                        if not doctor_notification:
                            notification_success = False
                            logger.warning(f"Failed to create notification for doctor: {doctor.name}")
                    
                    # Check if patient has a user account
                    if hasattr(patient, 'user') and patient.user:
                        # Notify Patient
                        patient_notification = create_notification(
                            recipient=patient.user,
                            message=f"Your appointment with Dr. {doctor.name} is scheduled for {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')} (booked by clinic staff).",
                            sender=request.user,
                            notification_type='appointment_new',
                            related_object=appointment
                        )
                        if not patient_notification:
                            notification_success = False
                            logger.warning(f"Failed to create notification for patient: {patient.get_full_name()}")
                    
                    # If either notification failed but didn't raise an exception
                    if not notification_success:
                        messages.warning(request, "Appointment created, but some notifications may not have been sent.")
                        
                except Exception as e:
                    logger.error(f"Error creating notification in staff_create_appointment: {e}", exc_info=True)
                    messages.warning(request, "Appointment created, but failed to send notifications.")
                # --- End Notifications ---

                messages.success(request, 'Appointment created successfully!')
                return redirect('users:staff_appointment_detail', appointment_id=appointment.id)
            except (Patient.DoesNotExist, Doctor.DoesNotExist):
                messages.error(request, 'Invalid patient or doctor selected.')
            except Exception as e:
                messages.error(request, f'Error creating appointment: {str(e)}')
        
        context = {
            'patients': patients,
            'doctors': doctors,
            'clinic': clinic
        }
        
        return render(request, 'staff/create_appointment.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('users:staff_dashboard')

@login_required
def staff_dashboard(request):
    """Staff dashboard view"""
    try:
        # Check if user has staff profile
        if not hasattr(request.user, 'staff'):
            messages.error(request, "You don't have staff access")
            return redirect('users:login')
            
        staff = request.user.staff
        if not staff.clinic:
            messages.error(request, "No clinic assigned to your account")
            return redirect('users:login')
            
        # Get today's date
        today = timezone.now().date()
        
        # Get clinic's doctors
        doctors = Doctor.objects.filter(clinic=staff.clinic, is_active=True)
        if not doctors:
            messages.error(request, "No doctors found for your clinic")
            return redirect('users:staff_dashboard')
        
        # Get today's appointments
        todays_appointments = Appointment.objects.filter(
            doctor__in=doctors,
            appointment_date=today
        ).order_by('appointment_time')
        
        # Get pending appointments
        pending_appointments = Appointment.objects.filter(
            doctor__in=doctors,
            status='PENDING'
        ).order_by('appointment_date', 'appointment_time')
        
        # Get recent patients
        recent_patients = Patient.objects.filter(
            clinic=staff.clinic
        ).order_by('-created_at')[:5]
        
        # Get recent lab tests - using prescription relationship
        recent_tests = LabTest.objects.filter(
            prescription__doctor__in=[doctor.user for doctor in doctors]
        ).order_by('-created_at')[:5]
        
        context = {
            'staff': staff,
            'clinic': staff.clinic,
            'todays_appointments': todays_appointments,
            'pending_appointments': pending_appointments,
            'recent_patients': recent_patients,
            'recent_tests': recent_tests,
            'doctors': doctors
        }
        
        return render(request, 'staff/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Error accessing dashboard: {str(e)}')
        return redirect('users:login')

@login_required
@user_is_staff
def staff_appointment_detail(request, appointment_id):
    """View appointment details for staff"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        staff = request.user.staff
        
        # Check if staff has access to this appointment
        if appointment.doctor.clinic != staff.clinic:
            messages.error(request, "You don't have permission to view this appointment")
            return redirect('users:staff_dashboard')

        context = {
            'appointment': appointment,
            'patient': appointment.patient,
            'doctor': appointment.doctor,
            'staff': staff
        }
        
        return render(request, 'staff/appointment_detail.html', context)

    except Exception as e:
        messages.error(request, f'Error viewing appointment: {str(e)}')
        return redirect('users:staff_dashboard')

@login_required
@user_is_staff
def staff_update_appointment(request, appointment_id):
    """Update appointment details"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        staff = request.user.staff
        
        # Check if staff has access to this appointment
        if appointment.doctor.clinic != staff.clinic:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        if request.method == 'POST':
            form = StaffAppointmentForm(request.POST, instance=appointment, clinic=staff.clinic)
            if form.is_valid():
                form.save()
                return JsonResponse({"status": "success"})
            return JsonResponse({"error": form.errors}, status=400)
        
        form = StaffAppointmentForm(instance=appointment, clinic=staff.clinic)
        return render(request, 'staff/appointment_edit.html', {'form': form, 'appointment': appointment})
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
@user_is_staff
def staff_cancel_appointment(request, appointment_id):
    """Cancel an appointment"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        staff = request.user.staff
        
        # Check if staff has access to this appointment
        if appointment.doctor.clinic != staff.clinic:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        if request.method == 'POST':
            appointment.status = 'cancelled'
            appointment.save()
            return JsonResponse({"status": "success"})
        
        return JsonResponse({"error": "Invalid request"}, status=400)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_appointments(request):
    """Get appointments for staff dashboard"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        appointments = Appointment.objects.filter(clinic=clinic)
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@login_required
def staff_patients(request):
    """View and manage patients for staff"""
    try:
        # Get staff's clinic
        if not hasattr(request.user, 'staff'):
            messages.error(request, "You don't have staff access")
            return redirect('users:dashboard')
            
        staff = request.user.staff
        if not staff.clinic:
            messages.error(request, "No clinic assigned to your account")
            return redirect('users:dashboard')
            
        # Get patients for the staff's clinic
        patients = Patient.objects.filter(clinic=staff.clinic).order_by('-created_at')
        
        # Get search parameters
        search_query = request.GET.get('search', '')
        if search_query:
            patients = patients.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(email__icontains=search_query)
            )
            
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        if status_filter:
            patients = patients.filter(status=status_filter)
            
        # Get sort parameters
        sort_by = request.GET.get('sort', '-created_at')
        if sort_by in ['name', '-name', 'created_at', '-created_at']:
            patients = patients.order_by(sort_by)
            
        context = {
            'patients': patients,
            'search_query': search_query,
            'status_filter': status_filter,
            'sort_by': sort_by,
            'clinic': staff.clinic
        }
        
        return render(request, 'staff/patients.html', context)
        
    except Exception as e:
        messages.error(request, f'Error accessing patients: {str(e)}')
        return redirect('users:staff_dashboard')

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_prescriptions(request):
    """Get prescriptions for staff dashboard"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        prescriptions = Prescription.objects.filter(clinic=clinic)
        serializer = PrescriptionSerializer(prescriptions, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_lab_tests(request):
    """List all lab tests for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        # Get clinic's doctors
        doctors = Doctor.objects.filter(clinic=clinic)
        
        # Get lab tests through prescription relationship
        lab_tests = LabTest.objects.filter(
            prescription__doctor__in=[doctor.user for doctor in doctors]
        ).select_related(
            'prescription__doctor',
            'prescription__patient',
            'test_definition'
        ).order_by('-created_at')
        
        context = {
            'lab_tests': lab_tests
        }
        
        return render(request, 'staff/Lab-tests.html', context)
    except Exception as e:
        messages.error(request, f'Error listing lab tests: {str(e)}')
        return redirect('users:staff_dashboard')

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_billing(request):
    """Get billing records for staff dashboard"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        # Get clinic's doctors
        doctors = Doctor.objects.filter(clinic=clinic)
        
        # Get billing records through appointment relationship
        billing = Billing.objects.filter(
            appointment__doctor__in=doctors
        ).select_related(
            'appointment__doctor',
            'appointment__patient'
        ).order_by('-created_at')
        
        serializer = BillingSerializer(billing, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsStaff])
def create_appointment(request):
    """Create new appointment"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        data = request.data
        data['clinic'] = clinic.id
        
        serializer = AppointmentSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsStaff])
def create_lab_test(request):
    """Create new lab test"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        data = request.data
        data['clinic'] = clinic.id
        
        serializer = LabTestSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsStaff])
def create_billing(request):
    """Create new billing record"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        data = request.data
        data['clinic'] = clinic.id
        
        serializer = BillingSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@login_required
@user_is_staff
def staff_billing_detail(request, billing_id):
    """View billing details for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        billing = get_object_or_404(Billing, id=billing_id, appointment__doctor__clinic=clinic)
        
        context = {
            'billing': billing,
            'clinic': clinic
        }
        
        return render(request, 'staff/billing_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error viewing billing: {str(e)}')
        return redirect('users:staff_billing')

@login_required
@user_is_staff
def staff_update_billing(request, billing_id):
    """Update billing record for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        billing = get_object_or_404(Billing, id=billing_id, appointment__doctor__clinic=clinic)
        
        if request.method == 'POST':
            serializer = BillingSerializer(billing, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                messages.success(request, 'Billing record updated successfully!')
                return redirect('users:staff_billing_detail', billing_id=billing.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            serializer = BillingSerializer(billing)
        
        context = {
            'billing': billing,
            'clinic': clinic,
            'form': serializer
        }
        
        return render(request, 'staff/update_billing.html', context)
    except Exception as e:
        messages.error(request, f'Error updating billing: {str(e)}')
        return redirect('users:staff_billing')

@login_required
@user_is_staff
def staff_delete_billing(request, billing_id):
    """Delete billing record for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        billing = get_object_or_404(Billing, id=billing_id, appointment__doctor__clinic=clinic)
        
        if request.method == 'POST':
            try:
                billing.delete()
                messages.success(request, 'Billing record deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting billing: {str(e)}')
        
        return redirect('users:staff_billing')
    except Exception as e:
        messages.error(request, f'Error deleting billing: {str(e)}')
        return redirect('users:staff_billing')

@login_required
@user_is_staff
def staff_patient_detail(request, patient_id):
    """View patient details for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        patient = get_object_or_404(Patient, id=patient_id, clinic=clinic)
        
        # Get patient's recent appointments
        recent_appointments = Appointment.objects.filter(
            patient=patient,
            doctor__clinic=clinic
        ).order_by('-appointment_date')[:5]
        
        # Get patient's recent lab tests
        recent_tests = LabTest.objects.filter(
            patient=patient,
            doctor__clinic=clinic
        ).order_by('-created_at')[:5]
        
        # Get patient's recent bills
        recent_bills = Billing.objects.filter(
            patient=patient,
            appointment__doctor__clinic=clinic
        ).order_by('-created_at')[:5]
        
        context = {
            'patient': patient,
            'clinic': clinic,
            'recent_appointments': recent_appointments,
            'recent_tests': recent_tests,
            'recent_bills': recent_bills
        }
        
        return render(request, 'staff/patient_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error viewing patient: {str(e)}')
        return redirect('users:staff_patients')

@login_required
@user_is_staff
def staff_lab_test_detail(request, test_id):
    """View lab test details for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        lab_test = get_object_or_404(LabTest, id=test_id, doctor__clinic=clinic)
        
        # Get related appointment if exists
        appointment = None
        if hasattr(lab_test, 'appointment'):
            appointment = lab_test.appointment
        
        # Get related prescription if exists
        prescription = None
        if hasattr(lab_test, 'prescription'):
            prescription = lab_test.prescription
        
        context = {
            'lab_test': lab_test,
            'clinic': clinic,
            'appointment': appointment,
            'prescription': prescription
        }
        
        return render(request, 'staff/lab_test_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error viewing lab test: {str(e)}')
        return redirect('users:staff_lab_tests')

@login_required
@user_is_staff
def staff_update_lab_test(request, test_id):
    """Update lab test for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        lab_test = get_object_or_404(LabTest, id=test_id, doctor__clinic=clinic)
        
        if request.method == 'POST':
            serializer = LabTestSerializer(lab_test, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                messages.success(request, 'Lab test updated successfully!')
                return redirect('users:staff_lab_test_detail', test_id=lab_test.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            serializer = LabTestSerializer(lab_test)
        
        context = {
            'lab_test': lab_test,
            'clinic': clinic,
            'form': serializer
        }
        
        return render(request, 'staff/update_lab_test.html', context)
    except Exception as e:
        messages.error(request, f'Error updating lab test: {str(e)}')
        return redirect('users:staff_lab_tests')

@login_required
@user_is_staff
def staff_delete_lab_test(request, test_id):
    """Delete lab test for staff"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        lab_test = get_object_or_404(LabTest, id=test_id, doctor__clinic=clinic)
        
        if request.method == 'POST':
            try:
                lab_test.delete()
                messages.success(request, 'Lab test deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting lab test: {str(e)}')
        
        return redirect('users:staff_lab_tests')
    except Exception as e:
        messages.error(request, f'Error deleting lab test: {str(e)}')
        return redirect('users:staff_lab_tests')

@login_required
@user_is_staff
def staff_calendar_events(request):
    """Get appointments and doctor availability for calendar view"""
    try:
        staff = request.user.staff
        clinic = staff.clinic

        # Get doctor filter if provided
        doctor_id = request.GET.get('doctor_id')

        # Get date range if provided, otherwise default to current month
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')
        
        try:
            if start_date_str:
                # Convert ISO format string to datetime
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                # Extract just the date part for appointment filtering
                start_date_for_query = start_date.date()
            else:
                # Default to start of current month
                today = timezone.now().date()
                start_date = datetime(today.year, today.month, 1)
                start_date_for_query = start_date.date()
                
            if end_date_str:
                # Convert ISO format string to datetime
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                # Extract just the date part for appointment filtering
                end_date_for_query = end_date.date()
            else:
                # Default to end of current month
                next_month = start_date.replace(day=28) + timedelta(days=4)
                end_date = next_month.replace(day=1) - timedelta(days=1)
                end_date_for_query = end_date.date()
        except ValueError:
            # Handle invalid date format
            start_date = timezone.now()
            start_date_for_query = start_date.date()
            end_date_for_query = (start_date + timedelta(days=30)).date()

        # Base queryset for appointments
        appointments = Appointment.objects.filter(
            doctor__clinic=clinic,
            appointment_date__gte=start_date_for_query,
            appointment_date__lte=end_date_for_query
        ).select_related('doctor', 'patient')

        # Apply doctor filter if provided
        if doctor_id:
            appointments = appointments.filter(doctor_id=doctor_id)

        # Get doctors for the clinic
        doctors = Doctor.objects.filter(clinic=clinic, is_active=True)

        # Get doctor availability for the date range
        doctor_availability = {}
        for doctor in doctors:
            availability = DoctorAvailability.objects.filter(
                doctor=doctor
            )

            slots = []
            for a in availability:
                # Generate slots for each day in the range
                # Make sure we're working with date objects consistently
                current_date = start_date_for_query
                while current_date <= end_date_for_query:
                    if current_date.weekday() == a.day_of_week:
                        slots.extend(a.generate_slots(current_date))
                    current_date += timedelta(days=1)

            doctor_availability[doctor.id] = slots

        # Convert appointments to calendar events
        events = []
        for appointment in appointments:
            try:
                patient_name = appointment.patient.get_full_name() if appointment.patient else "No Patient"
                doctor_name = appointment.doctor.name if appointment.doctor else "No Doctor"

                # Combine date and time into datetime objects
                start_datetime = datetime.combine(appointment.appointment_date, appointment.appointment_time)
                end_datetime = start_datetime + timedelta(minutes=30)

                event = {
                    'id': appointment.id,
                    'title': f"{patient_name} - Dr. {doctor_name}",
                    'start': start_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end': end_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                    'status': appointment.status,
                    'patient': patient_name,
                    'doctor': doctor_name,
                    'reason': appointment.reason,
                    'token_number': appointment.token_number
                }
                events.append(event)
            except (AttributeError, TypeError) as e:
                logger.error(f"Error processing appointment {appointment.id}: {str(e)}")
                continue

        # Prepare available slots for the template
        available_slots = []
        for doctor_id, slots in doctor_availability.items():
            doctor_obj = next((d for d in doctors if d.id == doctor_id), None)
            if not doctor_obj:
                continue
                
            for slot in slots:
                # Check if there is an appointment at this time
                # Extract date and time from the datetime slot object
                slot_date = slot.date()
                slot_time = slot.time()
                
                appointment_exists = appointments.filter(
                    appointment_date=slot_date,
                    appointment_time=slot_time,
                    doctor_id=doctor_id
                ).exists()

                if not appointment_exists:
                    available_slots.append({
                        'id': f"available_{doctor_id}_{slot.strftime('%Y%m%d%H%M')}",
                        'title': f"Available - Dr. {doctor_obj.name}",
                        'start': slot.strftime('%Y-%m-%dT%H:%M:%S'),
                        'end': (slot + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                        'status': 'AVAILABLE',
                        'doctor': doctor_obj.name,
                        'doctor_id': doctor_id,
                        'rendering': 'background',
                        'backgroundColor': '#e8f5e9'
                    })

        return JsonResponse({
            'events': events,
            'available_slots': available_slots
        })
    except Exception as e:
        logger.error(f"Error in staff_calendar_events: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@user_is_staff
def staff_calendar(request):
    """View staff calendar"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        doctors = Doctor.objects.filter(clinic=clinic, is_active=True)

        context = {
            'clinic': clinic,
            'doctors': doctors
        }
        return render(request, 'staff/calendar.html', context)
    except Exception as e:
        messages.error(request, f'Error accessing calendar: {str(e)}')
        return redirect('users:staff_dashboard')


@login_required
@user_is_staff
def staff_walk_in_appointment(request):
    """Handle walk-in appointments with token generation"""
    try:
        # Get staff's clinic
        staff = request.user.staff
        clinic = staff.clinic
            
        # Get clinic's doctors
        doctors = Doctor.objects.filter(clinic=staff.clinic, is_active=True)
        
        if request.method == 'POST':
            try:
                # Get form data
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                email = request.POST.get('email')
                phone_number = request.POST.get('phone_number')
                date_of_birth = request.POST.get('date_of_birth')
                gender = request.POST.get('gender')
                doctor_id = request.POST.get('doctor')
                appointment_date = request.POST.get('appointment_date')
                appointment_time = request.POST.get('appointment_time')
                reason = request.POST.get('reason')
                
                # Validate required fields
                if not all([first_name, last_name, phone_number, date_of_birth, gender, doctor_id, appointment_date, appointment_time]):
                    messages.error(request, "Please fill in all required fields")
                    return redirect('users:staff_walk_in_appointment')
                
                # Get doctor
                doctor = get_object_or_404(Doctor, id=doctor_id, clinic=staff.clinic)
                
                # Check if patient exists
                patient = Patient.objects.filter(
                    phone_number=phone_number,
                    clinic=staff.clinic
                ).first()
                
                if not patient:
                    # Create new patient
                    patient = Patient.objects.create(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone_number=phone_number,
                        date_of_birth=date_of_birth,
                        gender=gender,
                        clinic=staff.clinic
                    )
                    
                    # Create patient vitals
                    weight = request.POST.get('weight')
                    height = request.POST.get('height')
                    blood_type = request.POST.get('blood_type')
                    diabetes = request.POST.get('diabetes') == 'on'
                    hypertension = request.POST.get('hypertension') == 'on'
                    asthma = request.POST.get('asthma') == 'on'
                    allergies = request.POST.get('allergies')
                    
                    # Create vitals record
                    PatientVitals.objects.create(
                        patient=patient,
                        weight=weight,
                        height=height,
                        recorded_by=request.user
                    )
                    
                    # Update patient's medical history
                    existing_diseases = []
                    if diabetes:
                        existing_diseases.append('Diabetes')
                    if hypertension:
                        existing_diseases.append('Hypertension')
                    if asthma:
                        existing_diseases.append('Asthma')
                    
                    patient.existing_diseases = ', '.join(existing_diseases)
                    patient.allergies = allergies
                    patient.blood_group = blood_type
                    patient.save()
                
                # Generate token number for the day
                today = timezone.now().date()
                last_token = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=today
                ).order_by('-token_number').first()
                
                token_number = 1
                if last_token and last_token.token_number:
                    try:
                        token_number = int(last_token.token_number) + 1
                    except (ValueError, TypeError):
                        token_number = 1
                
                # Create appointment
                appointment = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reason=reason,
                    status='PENDING',
                    token_number=token_number,
                    is_walk_in=True
                )
                
                messages.success(request, f'Appointment created successfully! Token Number: {token_number}')
                return redirect('users:staff_appointment_detail', appointment_id=appointment.id)
                
            except Exception as e:
                messages.error(request, f'Error creating appointment: {str(e)}')
        
        # Get today's date and time
        today = timezone.now().date()
        current_time = timezone.now().time()

        context = {
            'doctors': doctors,
            'clinic': staff.clinic,
            'today': today,
            'current_time': current_time
        }
        
        return render(request, 'staff/walk_in_appointment.html', context)

    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('users:staff_dashboard')

@login_required
@user_is_staff
def staff_manage_leaves(request):
    """Manage staff leaves"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        # Get current year's leaves
        current_year = timezone.now().year
        leaves = StaffLeave.objects.filter(
            staff=staff,
            start_date__year=current_year
        ).order_by('-start_date')
        
        # Calculate leave statistics
        total_leaves = leaves.count()
        approved_leaves = leaves.filter(status='approved').count()
        pending_leaves = total_leaves - approved_leaves
        
        # Get upcoming leaves
        upcoming_leaves = leaves.filter(
            start_date__gte=timezone.now().date()
        ).order_by('start_date')
        
        # Handle leave request submission
        if request.method == 'POST':
            try:
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                leave_type = request.POST.get('leave_type')
                reason = request.POST.get('reason')
                
                # Validate dates
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if end_date < start_date:
                    messages.error(request, 'End date cannot be before start date')
                    return redirect('users:staff_manage_leaves')
                
                # Check for overlapping leaves
                overlapping_leaves = StaffLeave.objects.filter(
                    staff=staff,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    status__in=['pending', 'approved']
                )
                
                if overlapping_leaves.exists():
                    messages.error(request, 'You already have a leave request for these dates')
                    return redirect('users:staff_manage_leaves')
                
                # Create leave request
                leave = StaffLeave.objects.create(
                    staff=staff,
                    start_date=start_date,
                    end_date=end_date,
                    leave_type=leave_type,
                    reason=reason,
                    status='pending'
                )
                
                # Notify clinic admin
                admin_users = User.objects.filter(
                    is_staff=True,
                    clinic_admin__clinic=clinic
                )
                
                for admin in admin_users:
                    try:
                        create_notification(
                            recipient=admin,
                            message=f'{staff.user.get_full_name()} has requested leave from {start_date} to {end_date}',
                            notification_type='leave_request',
                            related_id=leave.id
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification to admin {admin}: {e}")
                        messages.warning(request, "Leave request submitted but failed to send notification to clinic admin.")
                
                messages.success(request, 'Leave request submitted successfully')
                return redirect('users:staff_manage_leaves')
                
            except Exception as e:
                messages.error(request, f'Error submitting leave request: {str(e)}')

        context = {
            'staff': staff,
            'clinic': clinic,
            'total_leaves': total_leaves,
            'approved_leaves': approved_leaves,
            'pending_leaves': pending_leaves,
            'upcoming_leaves': upcoming_leaves,
            'leave_types': StaffLeave.LEAVE_TYPE_CHOICES,
            'today': timezone.now().date()
        }
        
        return render(request, 'staff/manage_leaves.html', context)

    except Exception as e:
        messages.error(request, f'Error accessing leave management: {str(e)}')
        return redirect('users:staff_dashboard')
