from datetime import timedelta, timezone
import datetime
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404      
from ..models import Doctor, Appointment, Patient, Prescription, Clinic, Staff, ClinicAdmin
from ..serializers import AppointmentSerializer, DoctorSerializer1,PatientSerializer, PatientDetailsSerializer, PatientListSerializer, PrescriptionSerializer, DoctorSerializer, ClinicSerializer, MedicalHistorySerializer
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
from django.contrib.auth import get_user_model
import datetime as dt
from django.db.models import Case, When, Value, IntegerField, Count, Q
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
# Add this import
from notifications.utils import create_notification

logger = logging.getLogger(__name__)

User = get_user_model()

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
            # --- Add Notification ---
            try:
                create_notification(
                    recipient=appointment.patient.user,
                    message=f"Your appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date.strftime('%d-%b-%Y')} has been updated to: {new_status.capitalize()}.".format(new_status=new_status),
                    sender=request.user, # Doctor updating via API
                    notification_type='appointment_status_update',
                    related_object=appointment
                )
            except Exception as e:
                 logger.error(f"Error creating notification in API update_appointment_status: {e}")
                 # Don't block the API response for notification failure
            # --- End Notification ---
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
@permission_classes([IsAuthenticated])
def get_available_slots(request, doctor_id, date):
    """Get available slots for a doctor on a specific date"""
    try:
        # Get the doctor instance directly from Doctor model
        doctor = Doctor.objects.get(id=doctor_id)
        
        # Parse the date string using datetime.strptime
        try:
            appointment_date = dt.datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all existing appointments for this doctor on this date
        existing_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date
        ).values_list('appointment_time', flat=True)
        
        # Define all possible slots (9 AM to 5 PM)
        all_slots = [
            '09:00', '09:30', 
            '10:00', '10:30', 
            '11:00', '11:30',
            '14:00', '14:30',
            '15:00', '15:30',
            '16:00', '16:30'
        ]
        
        # Remove booked slots
        available_slots = [
            slot for slot in all_slots 
            if slot not in existing_appointments
        ]
        
        return Response({
            'available_slots': available_slots,
            'doctor_id': doctor_id,
            'date': date
        })
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Error in get_available_slots: {str(e)}")  # Debug log
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
            # --- Add Notification ---
            try:
                create_notification(
                    recipient=appointment.doctor.user,
                    message=f"Appointment with {appointment.patient.get_full_name()} on {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')} was cancelled by the patient.",
                    sender=request.user, # Patient cancelling via API
                    notification_type='appointment_cancelled',
                    related_object=appointment
                )
            except Exception as e:
                 logger.error(f"Error creating notification in API cancel_appointment: {e}")
                 # Don't block the API response for notification failure
            # --- End Notification ---
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
        # Verify user is a doctor
        if not request.user.groups.filter(name='Doctor').exists():
            return Response(
                {'error': 'User is not authorized as a doctor'}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        logger.info(f"Fetching appointments for doctor user: {request.user.username}")
        
        # Get the doctor from the authenticated user
        doctor = Doctor.objects.get(user=request.user)
        
        # Get appointments
        appointments = Appointment.objects.filter(
            doctor=doctor
        ).order_by('appointment_date')
        
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
        
        # Get current date
        today = timezone.now().date()
        
        # Get appointments with custom ordering
        appointments = Appointment.objects.filter(
            patient=patient
        ).annotate(
            # Custom ordering field
            order=Case(
                # Upcoming scheduled appointments first
                When(
                    appointment_date__gte=today,
                    status='scheduled',
                    then=Value(1)
                ),
                # Past scheduled appointments second
                When(
                    appointment_date__lt=today,
                    status='scheduled',
                    then=Value(2)
                ),
                # Completed appointments third
                When(status='completed', then=Value(3)),
                # Cancelled appointments last
                When(status='cancelled', then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        ).order_by(
            'order',
            '-appointment_date',  # Most recent dates first within each status group
            'appointment_time'
        )
        
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
            # Get all users who are staff members for this clinic
            staff_users = User.objects.filter(
                is_staff=True,
                staff__clinic=clinic
            ).select_related('staff', 'userprofile')
            
            data = [{
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'is_active': user.is_active,
                'role': user.staff.role if hasattr(user, 'staff') else None,
                'phone_number': user.userprofile.phone_number if hasattr(user, 'userprofile') else None
            } for user in staff_users]
            
            return Response(data)
            
        elif request.method == 'POST':
            # Create new staff user
            user_data = {
                'email': request.data.get('email'),
                'first_name': request.data.get('first_name'),
                'last_name': request.data.get('last_name'),
                'is_staff': True,
                'is_active': True
            }
            
            user = User.objects.create_user(**user_data)
            
            # Create staff record
            Staff.objects.create(
                user=user,
                clinic=clinic,
                role=request.data.get('role')
            )
            
            return Response({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'role': request.data.get('role'),
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
    return JsonResponse(staff.values())

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
def create_doctor_profile(request):
    try:
        # Get clinic_id from request data
        clinic_id = request.data.get('clinic_id')
        if not clinic_id:
            return Response(
                {'error': 'Clinic ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the clinic
        try:
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            return Response(
                {'error': 'Clinic not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Create user for doctor
        username = f"dr_{request.data.get('license_number')}"
        email = request.data.get('email', '')
        
        # Create User instance
        user = User.objects.create_user(
            username=username,
            email=email,
            password=make_password(request.data.get('license_number'))  # Temporary password
        )
        
        # Add to doctor group - with error handling
        doctor_group, created = Group.objects.get_or_create(name='Doctor')
        user.groups.add(doctor_group)

        # Create doctor profile
        doctor_data = {
            'user': user,
            'clinic': clinic,
            'name': request.data.get('name'),
            'license_number': request.data.get('license_number'),
            'medical_council': request.data.get('medical_council'),
            'specialization': request.data.get('specialization'),
            'consultation_fee': request.data.get('consultation_fee'),
            'verification_details': request.data.get('verification_details', {}),
        }

        # Handle profile picture if provided
        if 'profile_picture' in request.FILES:
            doctor_data['profile_picture'] = request.FILES['profile_picture']

        doctor = Doctor.objects.create(**doctor_data)

        return Response(
            DoctorSerializer(doctor).data,
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Error creating doctor profile: {str(e)}")
        # If user was created but doctor profile failed, cleanup
        if 'user' in locals():
            user.delete()
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_patients(request):
    """Get doctor's patients"""
    try:
        logger.info(f"Doctor patients request from user: {request.user.username}")
        logger.info(f"User groups: {[g.name for g in request.user.groups.all()]}")
        
        # Get the doctor profile
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            logger.error(f"No doctor profile found for user: {request.user.username}")
            return Response(
                {'error': 'Doctor profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all patients for this doctor using the appointments relationship
        patients = Patient.objects.filter(
            appointments__doctor=doctor
        ).distinct()
        
        logger.info(f"Found {patients.count()} patients for doctor {doctor.name}")
        
        patient_data = [{
            'id': patient.id,
            'first_name': patient.first_name,
            'last_name': patient.last_name,
            'age': patient.get_age(),  # Use get_age() method instead of age attribute
            'gender': patient.gender,
            'phone': patient.phone_number,
            'email': patient.email,
            'address': patient.address,
            'blood_group': patient.blood_group,
            'allergies': patient.allergies,
            'existing_diseases': patient.existing_diseases,
            'created_at': patient.created_at.isoformat() if patient.created_at else None,
        } for patient in patients]
        
        # Debug log
        logger.info(f"Sample patient data: {patient_data[0] if patient_data else 'No patients'}")
        
        return Response(patient_data)
        
    except Exception as e:
        logger.error(f"Error fetching patients: {str(e)}")
        logger.exception("Full traceback:")  # Add full traceback logging
        return Response(
            {'error': 'Failed to fetch patients'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_medical_history_api(request):
    patient = Patient.objects.get(user=request.user)
    medical_history = medical_history.objects.filter(patient=patient)
    serializer = MedicalHistorySerializer(medical_history, many=True)
    return Response(serializer.data)

@csrf_exempt  # Only if absolutely necessary
@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def create_appointment(request):
    """Create a new appointment"""
    try:
        data = request.data
        patient = get_object_or_404(Patient, user=request.user)
        doctor = get_object_or_404(Doctor, id=data.get('doctor'))

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=data.get('appointment_date'),
            appointment_time=data.get('appointment_time'),
            reason=data.get('reason'),
            status='scheduled'
        )

        # --- Add Notification --- 
        try:
            create_notification(
                recipient=appointment.doctor.user,
                message=f"New appointment booked by {appointment.patient.get_full_name()} for {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}.",
                sender=request.user, # Patient using the API
                notification_type='appointment_new',
                related_object=appointment
            )
        except Exception as e:
            logger.error(f"Error creating notification in API create_appointment: {e}")
            # Don't block the API response for notification failure
        # --- End Notification ---

        return Response({
            'message': 'Appointment created successfully',
            'id': appointment.id
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_staff_role(request, clinic_id, staff_id):
    """Update staff role for a specific clinic"""
    try:
        clinic = Clinic.objects.get(id=clinic_id)
        staff_user = User.objects.get(
            id=staff_id,
            is_staff=True,
            staff__clinic=clinic
        )
        
        new_role = request.data.get('role')
        if not new_role:
            return Response(
                {'error': 'Role is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        staff_user.staff.role = new_role
        staff_user.staff.save()
        
        return Response({
            'id': staff_user.id,
            'first_name': staff_user.first_name,
            'last_name': staff_user.last_name,
            'role': new_role,
            'message': 'Staff role updated successfully'
        })
        
    except Clinic.DoesNotExist:
        return Response(
            {'error': 'Clinic not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except User.DoesNotExist:
        return Response(
            {'error': 'Staff member not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating staff role: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinics(request):
    """Get all clinics for clinic admin"""
    try:
        # Get clinics where the user is an admin
        clinics = Clinic.objects.filter(clinic_admin=request.user)
        
        clinic_data = [{
            'id': clinic.id,
            'name': clinic.name,
            'address': clinic.address,
            'phone_number': clinic.phone_number,
            'email': clinic.email,
            'registration_number': clinic.registration_number,
            'logo': clinic.logo.url if clinic.logo else None,
            
        } for clinic in clinics]
         
        return Response(clinic_data)
    except Exception as e:
        print(f"Error fetching clinics: {str(e)}")  # Debug log
        return Response(
            {'error': 'Failed to fetch clinics'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinic_patients(request, clinic_id):
    """Get all patients for a specific clinic"""
    try:
        # Verify clinic exists and user has access
        clinic = get_object_or_404(Clinic, id=clinic_id)
        
        # Get patients for this clinic with related doctor info
        patients = Patient.objects.filter(clinic=clinic).select_related('doctor')
        
        # Serialize the data
        serializer = PatientListSerializer(patients, many=True)
        
        return Response(serializer.data)
    
    except Clinic.DoesNotExist:
        return Response(
            {'error': 'Clinic not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Patient list API error: {str(e)}")
        return Response(
            {'error': 'Failed to fetch patients'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['GET', 'PUT'])  
@permission_classes([IsAuthenticated])
def edit_patient_details(request, patient_id):
    try:    
        patient = get_object_or_404(Patient, id=patient_id)
        serializer = PatientDetailsSerializer(patient)
        return Response(serializer.data)
    except Patient.DoesNotExist:
        return Response(
            {'error': 'Patient not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_patient_details(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    serializer = PatientDetailsSerializer(patient, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinic_doctors(request, clinic_id):
    """Get doctors for a specific clinic"""
    try:
        logger.info(f"Fetching doctors for clinic: {clinic_id}")
        
        # Verify the clinic exists and user has access
        try:
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            logger.error(f"Clinic {clinic_id} not found")
            return Response(
                {'error': 'Clinic not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all doctors for this clinic
        doctors = Doctor.objects.filter(clinic=clinic)
        logger.info(f"Found {doctors.count()} doctors for clinic {clinic_id}")

        # Serialize the data
        serializer = DoctorSerializer(doctors, many=True)
        return Response(serializer.data)

    except Exception as e:
        logger.error(f"Error fetching clinic doctors: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([])  # No authentication required
def public_clinics_api(request):
    """Public API endpoint to get list of clinics for patient registration"""
    try:
        clinics = Clinic.objects.all()  # Remove is_active filter
        data = [{
            'id': clinic.id,
            'name': clinic.name,
            'address': clinic.address,
            'phone_number': clinic.phone_number,
            'email': clinic.email
        } for clinic in clinics]
        return Response(data)
    except Exception as e:
        logger.error(f"Error in public clinics API: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_dashboard_api(request):
    """API endpoint for doctor dashboard data"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        today = timezone.now().date()
        
        # Get today's appointments
        todays_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today
        ).select_related('patient').order_by('appointment_time')
        
        # Get upcoming appointments (next 7 days)
        upcoming_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gt=today,
            appointment_date__lte=today + timedelta(days=7)
        ).select_related('patient').order_by('appointment_date', 'appointment_time')[:10]
        
        # Calculate stats
        stats = {
            'todays_patients_count': todays_appointments.count(),
            'completed_today': todays_appointments.filter(status='completed').count(),
            'upcoming_count': Appointment.objects.filter(
                doctor=doctor,
                appointment_date__gt=today,
                status='scheduled'
            ).count(),
            'month_appointments_count': Appointment.objects.filter(
                doctor=doctor,
                appointment_date__month=today.month,
                appointment_date__year=today.year
            ).count(),
            'pending_count': Appointment.objects.filter(
                doctor=doctor,
                status='pending'
            ).count()
        }
        
        # Serialize appointments
        todays_serializer = AppointmentSerializer(todays_appointments, many=True)
        upcoming_serializer = AppointmentSerializer(upcoming_appointments, many=True)
        
        # Format doctor data manually to match React Native expectations
        doctor_data = {
            'id': doctor.id,
            'user': {
                'id': doctor.user.id,
                'first_name': doctor.user.first_name,
                'last_name': doctor.user.last_name,
                'email': doctor.user.email,
            },
            'specialization': doctor.specialization or 'General Practitioner',
            'clinic': {
                'id': doctor.clinic.id if doctor.clinic else None,
                'name': doctor.clinic.name if doctor.clinic else 'No clinic assigned'
            } if doctor.clinic else None,
            'license_number': doctor.license_number,
            'consultation_fee': getattr(doctor, 'consultation_fee', 0)
        }
        
        return Response({
            'doctor': doctor_data,
            'stats': stats,
            'todays_appointments': todays_serializer.data,
            'upcoming_appointments': upcoming_serializer.data
        })
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in doctor_dashboard_api: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_patients_api(request):
    """API endpoint for doctor's patients list"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        
        # Get patients who have appointments with this doctor
        patients = Patient.objects.filter(
            appointment__doctor=doctor
        ).distinct().select_related('user')
        
        serializer = PatientSerializer(patients, many=True)
        
        return Response({
            'patients': serializer.data
        })
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in doctor_patients_api: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_detail_api(request, patient_id):
    """API endpoint for patient details"""
    try:
        # Check if user is doctor and get patient
        doctor = get_object_or_404(Doctor, user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Check if doctor has treated this patient
        has_appointment = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).exists()
        
        if not has_appointment:
            return Response(
                {'error': 'You do not have access to this patient'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PatientDetailsSerializer(patient)
        
        return Response(serializer.data)
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Patient.DoesNotExist:
        return Response(
            {'error': 'Patient not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in patient_detail_api: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_records_api(request, patient_id):
    """API endpoint for patient records"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Check if doctor has access to this patient
        has_appointment = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).exists()
        
        if not has_appointment:
            return Response(
                {'error': 'You do not have access to this patient'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get appointments
        appointments = Appointment.objects.filter(
            patient=patient,
            doctor=doctor
        ).order_by('-appointment_date')
        
        # Get prescriptions
        prescriptions = Prescription.objects.filter(
            patient=patient,
            doctor=doctor
        ).order_by('-created_at')
        
        # Serialize data
        appointments_serializer = AppointmentSerializer(appointments, many=True)
        prescriptions_serializer = PrescriptionSerializer(prescriptions, many=True)
        
        return Response({
            'appointments': appointments_serializer.data,
            'prescriptions': prescriptions_serializer.data,
            'tests': []  # Add lab tests when implemented
        })
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Patient.DoesNotExist:
        return Response(
            {'error': 'Patient not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in patient_records_api: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def appointment_actions_api(request, appointment_id):
    """API endpoint for appointment actions (attend, complete, no_show)"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        action = request.data.get('action') or request.POST.get('action')
        
        if not action:
            return Response(
                {'error': 'Action is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Map actions to status
        status_mapping = {
            'attend': 'in_progress',
            'complete': 'completed',
            'no_show': 'no_show'
        }
        
        if action not in status_mapping:
            return Response(
                {'error': 'Invalid action'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update appointment status
        old_status = appointment.status
        new_status = status_mapping[action]
        appointment.status = new_status
        appointment.save()
        
        # Create notification
        try:
            status_messages = {
                'in_progress': f"Dr. {doctor.user.get_full_name()} has started attending your appointment",
                'completed': f"Your appointment with Dr. {doctor.user.get_full_name()} has been completed",
                'no_show': f"You were marked as no-show for your appointment with Dr. {doctor.user.get_full_name()}"
            }
            
            create_notification(
                recipient=appointment.patient.user,
                message=status_messages.get(new_status, f"Your appointment status has been updated to {new_status}"),
                sender=request.user,
                notification_type='appointment_status_update',
                related_object=appointment
            )
        except Exception as e:
            logger.error(f"Error creating notification in appointment_actions_api: {e}")
        
        return Response({
            'success': True,
            'message': f'Appointment {action} successfully',
            'new_status': new_status,
            'new_status_display': new_status.replace('_', ' ').title()
        })
        
    except Doctor.DoesNotExist:
        return Response(
            {'error': 'Doctor profile not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Appointment.DoesNotExist:
        return Response(
            {'error': 'Appointment not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error in appointment_actions_api: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def patient_vitals_api(request, patient_id):
    """API endpoint for patient vitals (placeholder)"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        patient = get_object_or_404(Patient, id=patient_id)
        has_appointment = Appointment.objects.filter(doctor=doctor, patient=patient).exists()
        if not has_appointment:
            return Response({'error': 'You do not have access to this patient'}, status=status.HTTP_403_FORBIDDEN)
        if request.method == 'GET':
            return Response({'vitals': []})
        elif request.method == 'POST':
            return Response({'success': True, 'message': 'Vitals saved successfully'})
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in patient_vitals_api: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_results_api(request, test_id):
    """API endpoint for test results (placeholder)"""
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        return Response({'test': {'id': test_id, 'name': 'Test Result', 'status': 'pending', 'result': None}})
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in test_results_api: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

