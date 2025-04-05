from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ..decorators import user_is_staff
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from ..forms import StaffAppointmentForm
from ..models import Appointment, Patient, Prescription, LabTest, Billing, Doctor, PatientVitals, StaffLeave, Notification
from ..serializers import AppointmentSerializer, PatientSerializer, PrescriptionSerializer, LabTestSerializer, BillingSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .permissions import IsStaff
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.contrib.auth.models import User

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
                notes = request.POST.get('notes')
                
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
                    notes=notes,
                    status='scheduled'
                )
                
                messages.success(request, 'Appointment created successfully!')
                return redirect('users:staff_appointment_detail', appointment_id=appointment.id)
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
            return redirect('users:dashboard')
            
        staff = request.user.staff
        if not staff.clinic:
            messages.error(request, "No clinic assigned to your account")
            return redirect('users:dashboard')
            
        # Get today's date
        today = timezone.now().date()
        
        # Get clinic's doctors
        doctors = Doctor.objects.filter(clinic=staff.clinic, is_active=True)
        
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
        
        # Get recent lab tests
        recent_tests = LabTest.objects.filter(
            doctor__in=doctors
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
        return redirect('users:dashboard')

@login_required
def staff_update_appointment(request, appointment_id):
    """Update an existing appointment"""
    if not hasattr(request.user, 'staff'):
        messages.error(request, "You don't have permission to update appointments.")
        return redirect('users:dashboard')
    
    staff = request.user.staff
    clinic = staff.clinic
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor__clinic=clinic)
    
    if request.method == 'POST':
        form = StaffAppointmentForm(request.POST, instance=appointment, clinic=clinic)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Appointment updated successfully!')
                return redirect('users:staff_dashboard')
            except Exception as e:
                messages.error(request, f'Error updating appointment: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StaffAppointmentForm(instance=appointment, clinic=clinic)
    
    return render(request, 'staff/update_appointment.html', {
        'form': form,
        'appointment': appointment,
        'clinic': clinic
    })

@login_required
def staff_cancel_appointment(request, appointment_id):
    """Cancel an appointment"""
    if not hasattr(request.user, 'staff'):
        messages.error(request, "You don't have permission to cancel appointments.")
        return redirect('users:dashboard')
    
    staff = request.user.staff
    clinic = staff.clinic
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor__clinic=clinic)
    
    if request.method == 'POST':
        try:
            appointment.status = 'cancelled'
            appointment.save()
            messages.success(request, 'Appointment cancelled successfully!')
        except Exception as e:
            messages.error(request, f'Error cancelling appointment: {str(e)}')
    
    return redirect('users:staff_dashboard')

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
    """Get lab tests for staff dashboard"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        lab_tests = LabTest.objects.filter(clinic=clinic)
        serializer = LabTestSerializer(lab_tests, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_billing(request):
    """Get billing records for staff dashboard"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        billing = Billing.objects.filter(clinic=clinic)
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

@api_view(['GET'])
@permission_classes([IsStaff])
def staff_calendar_events(request):
    """Get appointments for calendar view"""
    try:
        staff = request.user.staff
        clinic = staff.clinic
        
        # Get doctor filter if provided
        doctor_id = request.GET.get('doctor_id')
        
        # Base queryset
        appointments = Appointment.objects.filter(doctor__clinic=clinic)
        
        # Apply doctor filter if provided
        if doctor_id:
            appointments = appointments.filter(doctor_id=doctor_id)
        
        # Convert appointments to calendar events
        events = []
        for appointment in appointments:
            event = {
                'id': appointment.id,
                'title': f"{appointment.patient.get_full_name()} - {appointment.doctor.get_full_name()}",
                'start': appointment.appointment_date.strftime('%Y-%m-%d') + 'T' + appointment.appointment_time.strftime('%H:%M:%S'),
                'end': appointment.appointment_date.strftime('%Y-%m-%d') + 'T' + (appointment.appointment_time + timedelta(minutes=30)).strftime('%H:%M:%S'),
                'status': appointment.status
            }
            events.append(event)
        
        return Response(events)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
                    clinicadmin__clinic=clinic
                )
                
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        title='New Leave Request',
                        message=f'{staff.user.get_full_name()} has requested leave from {start_date} to {end_date}',
                        notification_type='leave_request',
                        related_id=leave.id
                    )
                
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