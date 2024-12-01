from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .serializers import UserProfileSerializer, SignupSerializer, LoginSerializer, PatientSerializer, AppointmentSerializer
from .models import UserProfile, Patient, Appointment
from .scripts import scrapper
import logging
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Function to generate JWT tokens for a user
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

@api_view(['POST'])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user:
        tokens = get_tokens_for_user(user)
        return Response({
            "message": "Login successful!",
            "access": tokens['access'],
            "is_email_verified": user.is_active,  # Assuming 'is_active' indicates email verification
        }, status=status.HTTP_200_OK)
    return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def signup_view(request):
    try:
        print("Received data:", request.data)  # Debug log

        # Extract all user data with exact field names from frontend
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        
        # Profile data with exact field names
        title = request.data.get('title')
        medical_degree = request.data.get('medical_degree')
        license_number = request.data.get('license_number')
        state_council = request.data.get('state_council')
        year_of_registration = request.data.get('year_of_registration')
        clinic_name = request.data.get('clinic_name')
        phone_number = request.data.get('phone_number')
        address = request.data.get('address')
        pincode = request.data.get('pincode')

        print("Extracted profile data:", {  # Debug log
            'title': title,
            'medical_degree': medical_degree,
            'license_number': license_number,
            'state_council': state_council,
            'clinic_name': clinic_name,
            'phone_number': phone_number,
            'address': address,
            'pincode': pincode
        })

        # Validate required fields
        if not all([username, email, password]):
            return Response(
                {"error": "Username, email, and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check existing user
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user first
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Wait for signal to create profile, then update it
        profile = user.userprofile
        profile.title = title
        profile.medical_degree = medical_degree
        profile.license_number = license_number
        profile.state_council = state_council
        profile.clinic_name = clinic_name
        profile.phone_number = phone_number
        profile.address = address
        profile.pincode = pincode
        profile.year_of_registration = year_of_registration
        profile.save()

        print(f"Updated profile for user: {username}")  # Debug log

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "Signup successful!",
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print("Error during signup:", str(e))  # Debug print
        return Response(
            {"error": f"An error occurred during signup: {str(e)}"},
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
@api_view(['POST'])
def verify_doctor(request):
    try:
        logger.info(f"Received verification request with data: {request.data}")
        
        # Extract data from request
        data = request.data
        name = data.get('name')
        registration_number = data.get('registration_number')
        state_council = data.get('state_council')

        # Validate required fields
        if not all([name, registration_number, state_council]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)

        doctor_details = {
            'name': name,
            'registration_number': registration_number,
            'state_council': state_council
        }

        logger.info(f"Attempting to verify doctor: {doctor_details}")
        success, result = scrapper.verify_doctor(doctor_details)
        
        if success:
            logger.info(f"Verification successful: {result}")
            return Response({
                'success': True,
                'data': result
            }, status=status.HTTP_200_OK)
        else:
            logger.error(f"Verification failed: {result}")
            return Response({
                'success': False,
                'error': result
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in verify_doctor: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def create_patient(request):
    serializer = PatientSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        # Log the errors for debugging
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_patients(request):
    patients = Patient.objects.all()
    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data)

class PatientsView(APIView):
    def post(self, request):
        serializer = PatientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AppointmentView(APIView):
    def post(self, request):
        serializer = AppointmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 