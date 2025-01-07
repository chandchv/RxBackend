from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, login, logout
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from ..serializers import UserProfileSerializer, SignupSerializer
from ..models import UserProfile, Doctor, Patient, Clinic
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.shortcuts import render, redirect
import json
from ..scripts import scrapeGpt01 as scrapper
from django.db import transaction, IntegrityError
from django.contrib import messages
from rest_framework.authtoken.models import Token
from ..forms import PatientSignupForm, DoctorSignupForm
from django.db.models import Max

@ensure_csrf_cookie
def login_view(request):
    """Handle user login through web interface"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(f"Login attempt for user: {username}")  # Debug print
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            print(f"User authenticated successfully: {user.username}")  # Debug print
            
            # Create or get token for API authentication
            token, _ = Token.objects.get_or_create(user=user)
            request.session['auth_token'] = token.key

            try:
                # First check if user is admin/staff
                if user.is_staff or user.is_superuser:
                    print(f"User {username} is admin/staff")  # Debug print
                    return redirect('users:clinic_admin_dashboard')
                
                # Then check if the user is a doctor
                elif Doctor.objects.filter(user=user).exists():
                    print(f"User {username} is a doctor")  # Debug print
                    return redirect('users:doctor_dashboard')
                
                # Then check if the user is a patient
                elif Patient.objects.filter(user=user).exists():
                    print(f"User {username} is a patient")  # Debug print
                    return redirect('users:patient_dashboard')
                
                else:
                    print(f"User {username} has no specific role")  # Debug print
                    messages.warning(request, 'User has no assigned role.')
                    return redirect('users:login')

            except Exception as e:
                print(f"Error during login redirection: {str(e)}")  # Debug print
                messages.error(request, f'Error during login: {str(e)}')
                return redirect('users:login')
        else:
            print(f"Authentication failed for user: {username}")  # Debug print
            messages.error(request, 'Invalid username or password.')
    
    # Show any messages in the template
    return render(request, 'login.html', {
        'next': request.GET.get('next', '')
    })


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    try:
        print("Received login request:", request.data)  # Debug print
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        print(f"Attempting login for user: {username}")  # Debug print
        
        if not username or not password:
            return Response({
                'error': 'Please provide both username and password'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        print(f"Authentication result: {user}")  # Debug print
        
        if user is not None:
            refresh = RefreshToken.for_user(user)
            
            # Determine user type
            user_type = 'unknown'
            additional_data = {}
            
            if hasattr(user, 'doctor'):
                user_type = 'doctor'
                additional_data = {
                    'doctor_id': user.doctor.id,
                    'clinic': user.doctor.clinic.name if user.doctor.clinic else None,
                }
            elif hasattr(user, 'patient'):
                user_type = 'patient'
                additional_data = {
                    'patient_id': user.patient.patient_id,  # Use patient_id instead of id
                }
            
            response_data = {
                'status': 'success',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': user_type,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                **additional_data
            }
            
            print("Sending successful response:", response_data)  # Debug print
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response({
            'status': 'error',
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except Exception as e:
        print(f"Login error: {str(e)}")  # Debug print
        return Response({
            'status': 'error',
            'error': 'An error occurred during login',
            'detail': str(e)
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
    
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_api(request):
    logout(request)
    return redirect('users:login')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')

def register_view(request):
    if request.method == 'POST':
        # Add your registration logic here
        pass
    return render(request, 'auth/register.html')

def generate_patient_id():
    """Generate a unique patient ID in the format PAT000001"""
    # Get the last patient ID
    last_patient = Patient.objects.all().order_by('-patient_id').first()
    
    if not last_patient or not last_patient.patient_id:
        # If no patients exist or last patient has no ID, start with PAT000001
        return 'PAT000001'
    
    try:
        # Extract the number from the last ID and increment it
        last_number = int(last_patient.patient_id[3:])
        new_number = last_number + 1
        # Create new ID with leading zeros
        new_id = f'PAT{new_number:06d}'
        return new_id
    except ValueError:
        # If there's any error, start with PAT000001
        return 'PAT000001'

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def patient_signup_api(request):
    try:
        print("Received patient signup data:", request.data)
        
        # Validate clinic
        clinic_id = request.data.get('clinic')
        try:
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive clinic selected"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
            # Generate patient ID
            patient_id = generate_patient_id()
            
            # Create user
            user = User.objects.create_user(
                username=request.data.get('username'),
                email=request.data.get('email'),
                password=request.data.get('password'),
                first_name=request.data.get('first_name'),
                last_name=request.data.get('last_name')
            )
            
            # Create patient profile with selected clinic and patient ID
            patient = Patient.objects.create(
                user=user,
                patient_id=patient_id,  # Add the generated ID
                clinic=clinic,
                phone_number=request.data.get('phone_number'),
                date_of_birth=request.data.get('date_of_birth'),
                gender=request.data.get('gender'),
                address=request.data.get('address'),
                blood_group=request.data.get('blood_group', '')
            )
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "message": "Patient signup successful!",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "patient": {
                    "patient_id": patient.patient_id,  # Include patient ID in response
                    "phone_number": patient.phone_number,
                    "gender": patient.gender,
                    "date_of_birth": patient.date_of_birth,
                    "clinic": clinic.name
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print("Exception during patient signup:", str(e))
        if 'user' in locals():
            try:
                user.delete()
            except:
                pass
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def patient_signup_view(request):
    """View function for patient signup page"""
    clinics = Clinic.objects.all()
    if request.method == 'GET':
        form = PatientSignupForm()
        return render(request, 'patient/patient_signup.html', {'form': form, 'clinics': clinics})
    
    elif request.method == 'POST':
        form = PatientSignupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    # Get the selected clinic
                    clinic_id = request.POST.get('clinic')
                    clinic = Clinic.objects.get(id=clinic_id)
                    
                    # Generate patient ID
                    patient_id = generate_patient_id()
                    
                    patient = Patient.objects.create(
                        user=user,
                        patient_id=patient_id,  # Add the generated ID
                        clinic=clinic,
                        phone_number=form.cleaned_data['phone_number'],
                        date_of_birth=form.cleaned_data['date_of_birth'],
                        gender=form.cleaned_data['gender'],
                        address=form.cleaned_data['address'],
                        blood_group=form.cleaned_data['blood_group']
                    )
                    messages.success(request, f'Registration successful! Your Patient ID is {patient_id}. Please login.')
                    return redirect('users:login')
            except Exception as e:
                messages.error(request, f'Error during registration: {str(e)}')
    else:
        form = PatientSignupForm()
    
    context = {
        'form': form,
        'clinics': clinics,
    }
    
    return render(request, 'patient/patient_signup.html', context)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def doctor_signup_api(request):
    try:
        print("Received doctor signup data:", request.data)
        
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
            
            # Create doctor profile
            doctor = Doctor.objects.create(
                user=user,
                title=request.data.get('title'),
                medical_degree=request.data.get('medical_degree'),
                license_number=request.data.get('license_number'),
                state_council=request.data.get('state_council'),
                clinic_name=request.data.get('clinic_name'),
                phone_number=request.data.get('phone_number'),
                clinic_address=request.data.get('clinic_address'),
                specialization=request.data.get('specialization')
            )
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "message": "Doctor signup successful!",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "doctor": {
                    "title": doctor.title,
                    "medical_degree": doctor.medical_degree,
                    "license_number": doctor.license_number,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print("Exception during doctor signup:", str(e))
        if 'user' in locals():
            user.delete()
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def doctor_signup_view(request):
    """View function for doctor signup page"""
    if request.method == 'POST':
        form = DoctorSignupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    doctor = Doctor.objects.create(
                        user=user,
                        title=form.cleaned_data['title'],
                        medical_degree=form.cleaned_data['medical_degree'],
                        license_number=form.cleaned_data['license_number'],
                        state_council=form.cleaned_data['state_council'],
                        clinic_name=form.cleaned_data['clinic_name'],
                        phone_number=form.cleaned_data['phone_number'],
                        clinic_address=form.cleaned_data['clinic_address'],
                        specialization=form.cleaned_data['specialization']
                    )
                    messages.success(request, 'Doctor registration successful! Please login.')
                    return redirect('users:login')
            except Exception as e:
                messages.error(request, f'Error during registration: {str(e)}')
    else:
        form = DoctorSignupForm()
    
    return render(request, 'doctor/doctor_signup.html', {'form': form})
def signup_view(request):
    """Handle user signup through web interface"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                return render(request, 'signup.html', {'error': 'Username already exists'})
            if User.objects.filter(email=email).exists():
                return render(request, 'signup.html', {'error': 'Email already exists'})
            
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Log the user in
            login(request, user)
            return redirect('users:doctor_dashboard')
            
        except Exception as e:
            return render(request, 'signup.html', {'error': str(e)})
    
    return render(request, 'signup.html')