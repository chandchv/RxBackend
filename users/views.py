# This file is kept for backward compatibility
# All views have been moved to the views/ directory

from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets

from .firebase_auth import FirebaseAuthentication
from .models import User
from .serializers import UserSerializer

from .views.auth_views import (
    signup, 
    user_login,
    user_logout,
    Dashboard,
    profile,
    doctor_signup, 
    dashboard,
    patient_detail,
    doctor_list,
    doctor_detail,
    appointment_create,
    appointment_detail,
    appointment_list,
    appointment_update,
    prescription_create,
    prescription_detail,
    prescription_list,
    appointment_calendar,
    cancel_appointment,
    patient_list,
    search_patients,
    drug_search,
    search_doctors,
    drug_suggestions,
)

from .views.prescription_views import (
    PrescriptionView,
    create_prescription,
    get_prescriptions,
    get_prescription,
    get_prescription_pdf,
    get_prescription_items,
    get_vitals,
    update_prescription,
    delete_prescription,
)

from .views.patient_views import (
    get_patient,
    get_patients,
    create_patient,
    update_patient,
    delete_patient,
    get_patient_prescriptions,
    search_patient,
    get_patient_appointments,
    PatientViewSet,
)

from .views.doctor_views import (
    get_doctor, 
    get_doctors,
    create_doctor,
    update_doctor,
    delete_doctor,
    DoctorViewSet,
)

from .views.appointment_views import (
    get_appointment,
    get_appointments,
    create_appointment,
    update_appointment,
    delete_appointment,
    get_doctor_appointments,
    get_patient_appointments,
    get_appointment_slots,
    book_appointment_slot,
    get_doctor_availability,
    set_doctor_availability,
    get_doctor_leaves,
    set_doctor_leave,
    AppointmentViewSet,
)

from .views.clinic_views import (
    get_clinic,
    get_clinics,
    create_clinic,
    update_clinic,
    delete_clinic,
    get_clinic_doctors,
    get_clinic_patients,
    get_clinic_appointments,
    get_clinic_prescriptions,
    ClinicViewSet,
)

from .views.staff_views import (
    get_staff,
    get_staffs,
    create_staff,
    update_staff,
    delete_staff,
    get_staff_leaves,
    set_staff_leave,
    StaffViewSet,
)

from .views.billing_views import (
    BillingViewSet,
    get_billing,
    get_billings,
    create_billing,
    update_billing,
    delete_billing,
    get_patient_billings,
    get_appointment_billing,
)

from .views.lab_views import LabTestViewSet
from .views.lab_management_views import LabManagementViewSet

# Authentication views
class FirebaseAuthView(APIView):
    """
    Authenticate users with Firebase ID token
    """
    permission_classes = [AllowAny]
    
    @csrf_exempt
    def post(self, request):
        try:
            id_token = request.data.get('id_token')
            if not id_token:
                return Response({'error': 'ID token is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify Firebase token
            decoded_token = FirebaseAuthentication.verify_firebase_token(id_token)
            
            # Get or create user
            user = FirebaseAuthentication.get_or_create_user(decoded_token)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Return user data and tokens
            return Response({
                'user': UserSerializer(user).data,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SocialAuthTokenView(APIView):
    """
    Exchange social auth for JWT tokens
    Used by mobile/frontend apps after authenticating with social providers
    """
    permission_classes = [AllowAny]
    
    @csrf_exempt
    def post(self, request):
        provider = request.data.get('provider')
        access_token = request.data.get('access_token')
        
        if not provider or not access_token:
            return Response({
                'error': 'Provider and access_token are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For simplicity, we'll use allauth's built-in mechanisms through a request
        # This would require proper integration with the social auth providers
        # In a real implementation, you might use the provider's API to verify the token
        
        # Get or create the user from the social provider's token
        if provider == 'google':
            # For demonstration - in a real app, verify with Google API
            # Example: google_user = google_verify_token(access_token)
            # Then find or create user based on google_user info
            
            # Stubbed implementation - would need real API calls
            email = request.data.get('email')
            if not email:
                return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'auth_provider': 'google',
                    'google_id': request.data.get('id', ''),
                    'first_name': request.data.get('first_name', ''),
                    'last_name': request.data.get('last_name', '')
                }
            )
            
            # If user exists but wasn't a Google user before
            if not created and user.auth_provider != 'google':
                user.auth_provider = 'google'
                user.google_id = request.data.get('id', '')
                user.save()
                
        elif provider == 'facebook':
            # Similar implementation for Facebook
            email = request.data.get('email')
            if not email:
                return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'auth_provider': 'facebook',
                    'facebook_id': request.data.get('id', ''),
                    'first_name': request.data.get('first_name', ''),
                    'last_name': request.data.get('last_name', '')
                }
            )
            
            # If user exists but wasn't a Facebook user before
            if not created and user.auth_provider != 'facebook':
                user.auth_provider = 'facebook'
                user.facebook_id = request.data.get('id', '')
                user.save()
        else:
            return Response({
                'error': f'Provider {provider} not supported'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        })

class RegisterView(APIView):
    """
    Register a new user with email and password
    """
    permission_classes = [AllowAny]
    
    @csrf_exempt
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response({
                'error': 'User with this email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            auth_provider='email'
        )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    """
    Login with email and password
    """
    permission_classes = [AllowAny]
    
    @csrf_exempt
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Authenticate user
        user = authenticate(email=email, password=password)
        
        if not user:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        })

class UserDeviceTokenView(APIView):
    """
    Update user's device token for push notifications
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        device_token = request.data.get('device_token')
        
        if not device_token:
            return Response({
                'error': 'Device token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Update user's device token
        user = request.user
        user.device_token = device_token
        user.save()
        
        return Response({'success': True})

# Make dashboard directly available at the module level
Dashboard = Dashboard.as_view()

# Keep all exports explicit for better code tracking
__all__ = [
    # Auth views
    'signup', 
    'user_login',
    'user_logout',
    'Dashboard',
    'profile',
    'doctor_signup', 
    'dashboard',
    'patient_detail',
    'doctor_list',
    'doctor_detail',
    'appointment_create',
    'appointment_detail',
    'appointment_list',
    'appointment_update',
    'prescription_create',
    'prescription_detail',
    'prescription_list',
    'appointment_calendar',
    'cancel_appointment',
    'patient_list',
    'search_patients',
    'drug_search',
    'search_doctors',
    'drug_suggestions',
    
    # Patient views
    'get_patient',
    'get_patients',
    'create_patient',
    'update_patient',
    'delete_patient',
    'get_patient_prescriptions',
    'search_patient',
    'get_patient_appointments',
    'PatientViewSet',
    
    # Appointment views
    'get_appointment',
    'get_appointments',
    'create_appointment',
    'update_appointment',
    'delete_appointment',
    'get_doctor_appointments',
    'get_patient_appointments',
    'get_appointment_slots',
    'book_appointment_slot',
    'get_doctor_availability',
    'set_doctor_availability',
    'get_doctor_leaves',
    'set_doctor_leave',
    'AppointmentViewSet',
    
    # Template views
    'signup_view',
    'login_view',
    'dashboard_view',
    'appointments_view',
    'profile_view',
    'logout_view',
    
    # Utils
    'get_tokens_for_user',
    'log_error',

    # Doctor views
    'get_doctor', 
    'get_doctors',
    'create_doctor',
    'update_doctor',
    'delete_doctor',
    'DoctorViewSet',
    
    # Prescription views
    'PrescriptionView',
    'get_prescriptions',
    'get_prescription',
    'get_prescription_pdf',
    'get_prescription_items',
    'get_vitals',
    'update_prescription',
    'delete_prescription',

    # Admin views
    'admin_dashboard',
    'drug_suggestions',
]

# Mock ViewSets to satisfy imports
class PatientViewSet(viewsets.ViewSet):
    pass

class DoctorViewSet(viewsets.ViewSet):
    pass

class AppointmentViewSet(viewsets.ViewSet):
    pass

class ClinicViewSet(viewsets.ViewSet):
    pass

class StaffViewSet(viewsets.ViewSet):
    pass

class BillingViewSet(viewsets.ViewSet):
    pass

class LabTestViewSet(viewsets.ViewSet):
    pass

class LabManagementViewSet(viewsets.ViewSet):
    pass
