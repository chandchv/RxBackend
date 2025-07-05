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