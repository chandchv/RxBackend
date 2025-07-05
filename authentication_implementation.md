# RxDoctor Custom Authentication Implementation

This document provides a detailed overview of the changes needed to implement custom user authentication with third-party providers (Google, Facebook, Firebase) in the RxDoctor application.

## Overview

The implementation adds custom user models and authentication mechanisms to support:
- Email/password authentication
- Google authentication
- Facebook authentication 
- Firebase authentication

## 1. Custom User Model

**File: `users/models.py`**

```python
class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """
    Custom User model that supports both traditional and third-party auth
    """
    # Keep first_name, last_name, password, and is_active from AbstractUser
    # Override the required fields
    username = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(unique=True)
    
    # Third-party authentication fields
    firebase_uid = models.CharField(max_length=150, blank=True, null=True)
    google_id = models.CharField(max_length=150, blank=True, null=True)
    facebook_id = models.CharField(max_length=150, blank=True, null=True)
    
    # Authentication method
    AUTH_CHOICES = (
        ('email', 'Email/Password'),
        ('google', 'Google'),
        ('facebook', 'Facebook'),
        ('firebase', 'Firebase'),
    )
    auth_provider = models.CharField(max_length=10, choices=AUTH_CHOICES, default='email')
    
    # Device info for push notifications
    device_token = models.TextField(blank=True, null=True)
    
    # Fix reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='rxdoctor_users_groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='rxdoctor_users_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    
    # Use email as the unique identifier for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
```

## 2. Django Settings

**File: `settings.py`**

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ...existing apps...
    "django.contrib.sites",  # Required for django-allauth
    # Third-party authentication apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    # ...
]

# Add to MIDDLEWARE
MIDDLEWARE = [
    # ...existing middleware...
    # Add allauth middleware
    'allauth.account.middleware.AccountMiddleware',
]

# Configure custom user model
AUTH_USER_MODEL = 'users.User'

# django-allauth settings
AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin
    'django.contrib.auth.backends.ModelBackend',
    # allauth specific authentication methods
    'allauth.account.auth_backends.AuthenticationBackend',
    # Firebase authentication
    'users.firebase_auth.FirebaseAuthBackend',
]

SITE_ID = 1

# allauth settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
ACCOUNT_UNIQUE_EMAIL = True

# Social account providers settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'FIELDS': [
            'id',
            'email',
            'name',
            'first_name',
            'last_name',
            'picture',
        ],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
    }
}

# Firebase Authentication
FIREBASE_AUTH = {
    'SERVICE_ACCOUNT_KEY_FILE': os.path.join(BASE_DIR, 'firebase-service-account.json'),
}
```

## 3. Custom Adapters for django-allauth

**File: `users/adapters.py`**

```python
from django.conf import settings
from django.contrib.auth import get_user_model
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

User = get_user_model()

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for django-allauth
    Handles standard email/password registration
    """
    def save_user(self, request, user, form, commit=True):
        """
        Saves a new user instance using information provided through allauth
        """
        user = super().save_user(request, user, form, commit=False)
        user.auth_provider = 'email'
        
        if commit:
            user.save()
        return user

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for django-allauth
    Handles social account registration (Google, Facebook)
    """
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a new user instance and connects it to the social account
        """
        user = super().save_user(request, sociallogin, form)
        
        # Set the auth provider based on the social account provider
        provider = sociallogin.account.provider
        if provider == 'google':
            user.auth_provider = 'google'
            user.google_id = sociallogin.account.uid
        elif provider == 'facebook':
            user.auth_provider = 'facebook'
            user.facebook_id = sociallogin.account.uid
        
        user.save()
        return user
```

## 4. Firebase Authentication

**File: `users/firebase_auth.py`**

```python
import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

# Initialize Firebase Admin SDK
cred = credentials.Certificate(settings.FIREBASE_AUTH['SERVICE_ACCOUNT_KEY_FILE'])
try:
    firebase_admin.initialize_app(cred)
except ValueError:
    # App already initialized
    pass

class FirebaseAuthentication:
    """
    Utilities for Firebase Auth verification and user retrieval
    """
    @staticmethod
    def verify_firebase_token(id_token):
        """
        Verify Firebase ID token and return the decoded token
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            raise AuthenticationFailed(f"Invalid Firebase token: {str(e)}")
    
    @staticmethod
    def get_or_create_user(decoded_token):
        """
        Get existing user or create a new one based on the Firebase token
        """
        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        if not email:
            raise AuthenticationFailed("Email is required for authentication")
        
        # Try to get the user by firebase_uid first
        try:
            user = User.objects.get(firebase_uid=firebase_uid)
            return user
        except User.DoesNotExist:
            # Then try to get the user by email
            try:
                user = User.objects.get(email=email)
                # User exists but doesn't have firebase_uid, update it
                user.firebase_uid = firebase_uid
                user.auth_provider = 'firebase'
                user.save()
                return user
            except User.DoesNotExist:
                # Create a new user
                user = User(
                    email=email,
                    firebase_uid=firebase_uid,
                    auth_provider='firebase',
                    is_active=True,
                )
                
                # Set other fields from token if available
                if 'name' in decoded_token:
                    name_parts = decoded_token['name'].split(' ', 1)
                    user.first_name = name_parts[0]
                    if len(name_parts) > 1:
                        user.last_name = name_parts[1]
                
                user.save()
                return user

class FirebaseAuthBackend(BaseBackend):
    """
    Django authentication backend for Firebase
    """
    def authenticate(self, request, firebase_token=None, **kwargs):
        if not firebase_token:
            return None
        
        try:
            decoded_token = FirebaseAuthentication.verify_firebase_token(firebase_token)
            user = FirebaseAuthentication.get_or_create_user(decoded_token)
            return user
        except AuthenticationFailed:
            return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
```

## 5. API Views for Authentication

**File: `users/views.py`**

```python
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
from .firebase_auth import FirebaseAuthentication
from .models import User
from .serializers import UserSerializer

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
        
        # Get or create the user from the social provider's token
        if provider == 'google':
            # For demonstration - in a real app, verify with Google API
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
```

## 6. User Serializer

**File: `users/serializers.py`**

```python
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'auth_provider', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'is_staff', 'is_superuser']
        extra_kwargs = {
            'password': {'write_only': True}
        }
```

## 7. URL Configuration

**File: `users/urls.py`**

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'users'

# API routes for custom authentication
api_auth_patterns = [
    path('register/', views.RegisterView.as_view(), name='api_register'),
    path('login/', views.LoginView.as_view(), name='api_login'),
    path('firebase/', views.FirebaseAuthView.as_view(), name='firebase_auth'),
    path('social-auth/', views.SocialAuthTokenView.as_view(), name='social_auth'),
    path('device-token/', views.UserDeviceTokenView.as_view(), name='device_token'),
]

# Add routes to allauth for social authentication in web views
allauth_patterns = [
    path('', include('allauth.urls')),
]

# Main web URLs
urlpatterns = [
    # Web routes
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    
    # Dashboard routes
    path('', views.Dashboard.as_view(), name='index'),
    
    # API auth routes
    path('api/auth/', include(api_auth_patterns)),
    
    # Social auth for web views
    path('accounts/', include(allauth_patterns)),
]
```

## 8. Adding Firebase Authentication to Your Project

1. Create a Firebase project at https://console.firebase.google.com/
2. Add a web app to your Firebase project
3. Download the Firebase service account key JSON and save it as `firebase-service-account.json` in your project root
4. Install the Firebase Admin SDK: `pip install firebase-admin`
5. Configure your Firebase project settings in Django settings.py

## 9. Adding Social Authentication

1. For Google authentication:
   - Register your app in the Google Developer Console and get OAuth credentials
   - Add the credentials to your Django allauth settings

2. For Facebook authentication:
   - Register your app on Facebook Developer portal and get OAuth credentials
   - Add the credentials to your Django allauth settings

## Implementation Steps

1. Install required packages:
   ```
   pip install django-allauth firebase-admin
   ```

2. Add custom User model to models.py
3. Configure settings.py
4. Create adapter classes for allauth
5. Set up Firebase authentication backend
6. Create API views for authentication
7. Configure URLs
8. Migrate the database
9. Update Django admin for the new User model
10. Test authentication flows

## Notes

The implementation requires careful database migration when replacing the built-in Django User model with a custom one, especially in an existing project. For a production application, you might need a more complex migration strategy involving data transfer from the old user model to the new one. 