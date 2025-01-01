from datetime import timedelta, timezone
import datetime
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from ..models import Doctor, Appointment, Patient, Prescription, Clinic, Staff, ClinicAdmin
from ..serializers import AppointmentSerializer, PatientListSerializer, PrescriptionSerializer, DoctorSerializer, ClinicSerializer
import logging
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from ..models import Patient, Prescription
from ..serializers import PrescriptionSerializer
import logging
from django.utils import timezone
from django.core.files.storage import default_storage
from ..models import UserProfile
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.parsers import MultiPartParser, FormParser
import json

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_list(request):
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        appointments = Appointment.objects.filter(doctor=doctor).order_by('appointment_date')
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_appointment_status(request, appointment_id):
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        new_status = request.data.get('status')
        if new_status in ['scheduled', 'completed', 'cancelled']:
            appointment.status = new_status
            appointment.save()
            return Response({'success': True})
        return Response(
            {'error': 'Invalid status'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def available_slots(request, doctor_id, date):
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get all booked appointments for the selected date
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__date=selected_date
        ).values_list('appointment_date__time', flat=True)
        
        # Generate available time slots (example: 9 AM to 5 PM, 30-minute intervals)
        all_slots = []
        start_time = timezone.datetime.combine(selected_date, timezone.datetime.min.time().replace(hour=9))
        end_time = timezone.datetime.combine(selected_date, timezone.datetime.min.time().replace(hour=17))
        
        current_slot = start_time
        while current_slot < end_time:
            if current_slot.time() not in booked_slots:
                all_slots.append(current_slot.strftime('%H:%M'))
            current_slot += timedelta(minutes=30)
        
        return Response({'slots': all_slots})
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400) 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_appointment(request, appointment_id):
    try:
        appointment = get_object_or_404(Appointment, 
                                      id=appointment_id, 
                                      patient__user=request.user)
        
        if appointment.status == 'scheduled':
            appointment.status = 'cancelled'
            appointment.save()
            return Response({'success': True})
        
        return Response(
            {'error': 'Appointment cannot be cancelled'}, 
            status=400
        )
        
    except Exception as e:
        return Response({'error': str(e)}, status=400) 

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_me(request):
    """Get current patient's information"""
    try:
        patient = Patient.objects.get(user=request.user)
        serializer = PatientSerializer(patient)
        return Response(serializer.data)
    except Patient.DoesNotExist:
        return Response(
            {'error': 'Patient profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_prescriptions(request):
    """Get patient's prescriptions"""
    try:
        logger.info(f"Fetching prescriptions for user: {request.user.username}")
        
        # Get the patient from the authenticated user
        patient = request.user.patient
        
        # Get prescriptions
        prescriptions = Prescription.objects.filter(
            patient=patient
        ).order_by('-created_at')
        
        logger.info(f"Found {prescriptions.count()} prescriptions")
        
        serializer = PrescriptionSerializer(prescriptions, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error fetching prescriptions: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_prescriptions_detail(request, pk):
    """Get patient's prescriptions details"""
    try:
        prescription = get_object_or_404(Prescription, id=pk, patient=request.user.patient)
        serializer = PrescriptionSerializer(prescription)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_me(request):
    """Get current doctor's information"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        serializer = DoctorSerializer(doctor)
        return Response(serializer.data)
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_appointments(request):
    """Get doctor's appointments"""
    try:
        logger.info(f"Fetching appointments for doctor user: {request.user.username}")
        
        # Get the doctor from the authenticated user
        doctor = Doctor.objects.get(user=request.user)
        
        # Get appointments
        appointments = Appointment.objects.filter(
            doctor=doctor
        ).order_by('appointment_date')
        
        logger.info(f"Found {appointments.count()} appointments for doctor")
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
        
    except Doctor.DoesNotExist:
        logger.error(f"No doctor profile found for user: {request.user.username}")
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching doctor appointments: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_appointments(request):
    """Get patient's appointments"""
    try:
        logger.info(f"Fetching appointments for patient user: {request.user.username}")
        
        # Get the patient from the authenticated user
        patient = Patient.objects.get(user=request.user)
        
        # Get appointments
        appointments = Appointment.objects.filter(
            patient=patient
        ).order_by('appointment_date')
        
        logger.info(f"Found {appointments.count()} appointments for patient")
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
        
    except Patient.DoesNotExist:
        logger.error(f"No patient profile found for user: {request.user.username}")
        return Response(
            {'error': 'Patient profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching patient appointments: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def clinic_profile_api(request):
    """Handle clinic profile operations"""
    try:
        # Get clinic based on user's role
        if hasattr(request.user, 'clinic_admin'):
            clinic = request.user.clinic_admin.clinic
        else:
            return Response(
                {'error': 'User is not authorized to access clinic profile'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'GET':
            data = {
                'Name': clinic.name,
                'address': clinic.address,
                'phone_number': clinic.phone_number,
                'email': clinic.email,
                'registration_number': clinic.registration_number,
                'logo': request.build_absolute_uri(clinic.logo.url) if clinic.logo else None
            }
            return Response(data)
            
        elif request.method == 'POST':
            # Handle logo upload
            if 'logo' in request.FILES:
                if clinic.logo:
                    # Delete old logo if it exists
                    try:
                        default_storage.delete(clinic.logo.path)
                    except Exception as e:
                        logger.warning(f"Failed to delete old logo: {e}")
                clinic.logo = request.FILES['logo']
            
            # Update other fields if provided
            if 'name' in request.data:
                clinic.name = request.data['name']
            if 'address' in request.data:
                clinic.address = request.data['address']
            if 'phone_number' in request.data:
                clinic.phone_number = request.data['phone_number']
            if 'email' in request.data:
                clinic.email = request.data['email']
            if 'registration_number' in request.data:
                clinic.registration_number = request.data['registration_number']
            
            clinic.save()
            
            data = {
                'name': clinic.name,
                'address': clinic.address,
                'phone_number': clinic.phone_number,
                'email': clinic.email,
                'registration_number': clinic.registration_number,
                'logo': request.build_absolute_uri(clinic.logo.url) if clinic.logo else None
            }
            return Response(data)
            
    except Exception as e:
        logger.error(f"Error in clinic profile: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_clinics_api(request):
    """Handle clinic listing and creation for superuser"""
    try:
        if request.method == 'GET':
            clinics = Clinic.objects.all()
            data = [{
                'id': clinic.id,
                'name': clinic.name,
                'address': clinic.address,
                'phone_number': clinic.phone_number,
                'email': clinic.email,
                'registration_number': clinic.registration_number,
                'doctors_count': clinic.doctor_set.count(),
                'staff_count': clinic.staff_set.count()
            } for clinic in clinics]
            return Response(data)
            
        elif request.method == 'POST':
            # Create new clinic
            clinic = Clinic.objects.create(
                name=request.data.get('name'),
                address=request.data.get('address'),
                phone_number=request.data.get('phone_number'),
                email=request.data.get('email'),
                registration_number=request.data.get('registration_number')
            )
            
            # Create clinic admin if admin details provided
            admin_data = request.data.get('admin')
            if admin_data:
                user = User.objects.create_user(
                    username=admin_data.get('username'),
                    email=admin_data.get('email'),
                    password=admin_data.get('password')
                )
                ClinicAdmin.objects.create(user=user, clinic=clinic)
            
            return Response({
                'id': clinic.id,
                'name': clinic.name,
                'message': 'Clinic created successfully'
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"Error in admin clinics: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_doctors_api(request, clinic_id):
    """Handle doctors for a specific clinic"""
    try:
        clinic = Clinic.objects.get(id=clinic_id)
        
        if request.method == 'GET':
            doctors = clinic.doctor_set.all()
            data = [{
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'license_number': doctor.license_number,
                'medical_council': doctor.medical_council,
                'verified': doctor.verified
            } for doctor in doctors]
            return Response(data)
            
        elif request.method == 'POST':
            # Create new doctor
            doctor = Doctor.objects.create(
                clinic=clinic,
                name=request.data.get('name'),
                specialization=request.data.get('specialization'),
                phone_number=request.data.get('phone_number'),
                email=request.data.get('email')
            )
            
            return Response({
                'id': doctor.id,
                'name': doctor.name,
                'message': 'Doctor added successfully'
            }, status=status.HTTP_201_CREATED)
            
    except Clinic.DoesNotExist:
        return Response({'error': 'Clinic not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in admin doctors: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_staff_api(request, clinic_id):
    """Handle staff for a specific clinic"""
    try:
        clinic = Clinic.objects.get(id=clinic_id)
        
        if request.method == 'GET':
            staff = clinic.staff_set.all()
            data = [{
                'id': staff_member.id,
                'name': staff_member.name,
                'role': staff_member.role,
                'phone_number': staff_member.phone_number,
                'email': staff_member.email
            } for staff_member in staff]
            return Response(data)
            
        elif request.method == 'POST':
            # Create new staff member
            staff = Staff.objects.create(
                clinic=clinic,
                name=request.data.get('name'),
                role=request.data.get('role'),
                phone_number=request.data.get('phone_number'),
                email=request.data.get('email')
            )
            
            return Response({
                'id': staff.id,
                'name': staff.name,
                'message': 'Staff member added successfully'
            }, status=status.HTTP_201_CREATED)
            
    except Clinic.DoesNotExist:
        return Response({'error': 'Clinic not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in admin staff: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinic_appointments_api(request, clinic_id):
    """Get all appointments for a specific clinic"""
    try:
        clinic = Clinic.objects.get(id=clinic_id)
        appointments = Appointment.objects.filter(doctor__clinic=clinic)
        
        data = [{
            'id': appointment.id,
            'patient_name': f"{appointment.patient.user.first_name} {appointment.patient.user.last_name}",
            'doctor_name': f"{appointment.doctor.user.first_name} {appointment.doctor.user.last_name}",
            'appointment_date': appointment.appointment_date,
            'status': appointment.status
        } for appointment in appointments]
        
        return Response(data)
        
    except Clinic.DoesNotExist:
        return Response(
            {'error': 'Clinic not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching appointments: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@ensure_csrf_cookie
@permission_classes([AllowAny])
def get_csrf_token(request):
    """
    Get CSRF token for making POST requests
    """
    return Response({'message': 'CSRF cookie set'})

@csrf_exempt  # Temporarily exempt this endpoint from CSRF
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_doctor(request):
    """
    Verify doctor credentials
    """
    logger.info("Received doctor verification request")
    logger.debug(f"Request data: {request.data}")
    
    try:
        # Extract data from request
        name = request.data.get('name')
        registration_number = request.data.get('registration_number')
        state_council = request.data.get('state_council')

        # Log received data
        logger.info(f"Verifying doctor: {name}, reg: {registration_number}, council: {state_council}")

        # Validate required fields
        if not all([name, registration_number, state_council]):
            logger.warning("Missing required fields in doctor verification request")
            return Response({
                'verified': False,
                'message': 'Please provide all required fields: name, registration_number, and state_council'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Mock verification data (replace with actual verification logic)
        verification_data = {
            'name': name,
            'registration_number': registration_number,
            'state_council': state_council,
            'qualification': 'MBBS',  # Example data
            'registration_date': '2020-01-01'  # Example data
        }

        logger.info(f"Doctor verification successful for: {name}")
        return Response({
            'verified': True,
            'verification_data': verification_data,
            'message': 'Doctor verified successfully'
        })

    except Exception as e:
        logger.error(f"Error in doctor verification: {str(e)}", exc_info=True)
        return Response({
            'verified': False,
            'message': f'Verification failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinic_appointments(request, clinic_id):
    """Get all appointments for a specific clinic"""
    appointments = Appointment.objects.filter(doctor__clinic_id=clinic_id)
    return Response(appointments.values())

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinic_doctors(request, clinic_id):
    """Get all doctors for a specific clinic"""
    doctors = Doctor.objects.filter(clinic_id=clinic_id)
    return Response(doctors.values())

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinic_staff(request, clinic_id):
    """Get all staff for a specific clinic"""
    staff = Staff.objects.filter(clinic_id=clinic_id)
    return Response(staff.values())

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_appointments(request, patient_id):
    """Get all appointments for a specific patient"""
    appointments = Appointment.objects.filter(patient_id=patient_id)
    return Response(appointments.values())

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctors(request):
    """Get all doctors"""
    doctors = Doctor.objects.all()
    return Response(doctors.values())



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_doctor_profile(request):
    """
    Create a new doctor profile after verification
    """
    logger.info("Received doctor profile creation request")
    
    try:
        # Get the clinic
        clinic_id = request.data.get('clinic')
        clinic = Clinic.objects.get(id=clinic_id)

        # Create or get user for the doctor
        email = request.data.get('email', '').lower()
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': request.data.get('name', '').split()[0],
                'last_name': ' '.join(request.data.get('name', '').split()[1:]),
                'is_active': True
            }
        )

        # Create doctor profile
        doctor = Doctor.objects.create(
            user=user,
            clinic=clinic,
            name=request.data.get('name'),
            specialization=request.data.get('specialization', ''),
            license_number=request.data.get('license_number'),
            medical_council=request.data.get('medical_council'),
            consultation_fee=request.data.get('consultation_fee', 0),
            verified=True,
            verification_details=json.loads(request.data.get('verification_details', '{}')),
        )

        # Handle profile picture if provided
        if 'profile_picture' in request.FILES:
            doctor.profile_picture = request.FILES['profile_picture']
            doctor.save()

        logger.info(f"Doctor profile created successfully: {doctor.name}")
        return Response({
            'id': doctor.id,
            'name': doctor.name,
            'message': 'Doctor profile created successfully'
        }, status=status.HTTP_201_CREATED)

    except Clinic.DoesNotExist:
        logger.error("Clinic not found")
        return Response({
            'message': 'Clinic not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error creating doctor profile: {str(e)}", exc_info=True)
        return Response({
            'message': f'Failed to create doctor profile: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_patients(request):
    try:
        # Get the doctor's clinic
        doctor = Doctor.objects.get(user=request.user)
        clinic = doctor.clinic
    except Doctor.DoesNotExist:
        return Response(
            {"error": "Doctor profile not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Clinic.DoesNotExist:
        return Response(
            {"error": "Clinic not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        # Get all patients in the doctor's clinic
        patients = Patient.objects.filter(clinic=clinic)
        serializer = PatientListSerializer(patients, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        # Add the clinic to the request data
        data = request.data.copy()
        data['clinic'] = clinic.id
        
        serializer = PatientListSerializer(data=data)
        if serializer.is_valid():
            patient = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)