from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .serializers import UserProfileSerializer, SignupSerializer, LoginSerializer
from .models import UserProfile
import logging

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
        phone_number = request.data.get('phone_number')
        address = request.data.get('address')
        pincode = request.data.get('pincode')

        print("Extracted profile data:", {  # Debug log
            'title': title,
            'medical_degree': medical_degree,
            'license_number': license_number,
            'state_council': state_council,
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
        profile.phone_number = phone_number
        profile.address = address
        profile.pincode = pincode
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