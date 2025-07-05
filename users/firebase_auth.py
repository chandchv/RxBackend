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