from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, login, logout
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from ..serializers import UserProfileSerializer, SignupSerializer
from ..models import UserProfile, Doctor, Patient
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.shortcuts import render, redirect
import json
from ..scripts import scrapeGpt01 as scrapper
from django.db import transaction, IntegrityError
from django.contrib import messages
from rest_framework.authtoken.models import Token

@ensure_csrf_cookie
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Create or get token for API authentication
            token, _ = Token.objects.get_or_create(user=user)
            request.session['auth_token'] = token.key

            try:
                # Check if the user is a doctor
                if Doctor.objects.filter(user=user).exists():
                    print("User is a doctor, redirecting to doctor dashboard")  # Debug print
                    return redirect('users:doctor_dashboard')
                
                # Check if the user is a patient
                elif Patient.objects.filter(user=user).exists():
                    print("User is a patient, redirecting to patient dashboard")  # Debug print
                    return redirect('users:patient_dashboard')
                
                else:
                    print("User has no specific role, redirecting to default dashboard")  # Debug print
                    return redirect('users:dashboard')

            except Exception as e:
                print(f"Error during login redirection: {str(e)}")  # Debug print
                messages.error(request, 'Error during login. Please try again.')
                return redirect('users:login')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'auth/login.html')

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    try:
        # Log the incoming request
        print("Login request data:", request.data)
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'error': 'Please provide both username and password'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'username': user.username,
                'email': user.email,
                'is_email_verified': user.is_active
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        print(f"Login error: {str(e)}")  # Log the error
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def signup_api(request):
    try:
        print("Received signup data:", request.data)
        
        # Check if username or email already exists
        if User.objects.filter(username=request.data.get('username')).exists():
            return Response(
                {"error": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=request.data.get('email')).exists():
            return Response(
                {"error": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=request.data.get('username'),
                email=request.data.get('email'),
                password=request.data.get('password'),
                first_name=request.data.get('first_name'),
                last_name=request.data.get('last_name')
            )
            
            # Delete any existing profile for this user (shouldn't exist, but just in case)
            UserProfile.objects.filter(user=user).delete()
            
            # Create new profile
            profile = UserProfile.objects.create(
                user=user,
                title=request.data.get('title', ''),
                medical_degree=request.data.get('medical_degree', ''),
                license_number=request.data.get('license_number', ''),
                state_council=request.data.get('state_council', ''),
                #year_of_registration=request.data.get('year_of_registration', ''),
                clinic_name=request.data.get('clinic_name', ''),
                phone_number=request.data.get('phone_number', ''),
                address=request.data.get('address', ''),
                pincode=request.data.get('pincode', '')
            )
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "message": "Signup successful!",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "profile": {
                    "title": profile.title,
                    "medical_degree": profile.medical_degree,
                    "license_number": profile.license_number,
                    "state_council": profile.state_council,
                    "clinic_name": profile.clinic_name,
                    "phone_number": profile.phone_number,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print("Exception during signup:", str(e))
        # If user was created but profile creation failed, delete the user
        if 'user' in locals():
            try:
                user.delete()
            except Exception:
                pass
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)
    except UserProfile.DoesNotExist:
        return Response(
            {"error": "Profile not found"}, 
            status=status.HTTP_404_NOT_FOUND
        ) 

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_doctor_api(request):
    try:
        print("Received verification request:", request.data)
        
        # Extract data
        name = request.data.get('name')
        registration_number = request.data.get('registration_number')
        state_council = request.data.get('state_council')

        # Validate required fields
        if not all([name, registration_number, state_council]):
            return Response({
                'success': False,
                'error': 'Please provide all required fields: name, registration_number, and state_council'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Call the scraper with proper data structure
        verification_data = {
            'name': name,
            'registration_number': registration_number,
            'state_council': state_council
        }
        
        print("Calling scraper with data:", verification_data)
        
        try:
            # Get the scraper result
            verification_result = scrapper.verify_doctor(verification_data)
            print("Raw scraper result:", verification_result)

            # Handle tuple response from scraper
            if isinstance(verification_result, tuple):
                success, data = verification_result
                if success:
                    return Response({
                        'success': True,
                        'data': {
                            'name': name,
                            'registration_number': registration_number,
                            'state_council': state_council,
                            'verification_details': data
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'error': str(data) if data else 'Verification failed'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle dictionary response
            elif isinstance(verification_result, dict):
                if verification_result.get('success'):
                    return Response({
                        'success': True,
                        'data': verification_result.get('data', {})
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'error': verification_result.get('error', 'Verification failed')
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            else:
                raise ValueError(f"Unexpected response type from scraper: {type(verification_result)}")

        except Exception as scraper_error:
            print(f"Scraper error: {str(scraper_error)}")
            return Response({
                'success': False,
                'error': f'Verification process failed: {str(scraper_error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        print(f"General error in verify_doctor_api: {str(e)}")
        return Response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')

def register_view(request):
    if request.method == 'POST':
        # Add your registration logic here
        pass
    return render(request, 'auth/register.html')