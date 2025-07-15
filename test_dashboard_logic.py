#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RxBackend.settings')
django.setup()

from labs.models import LabProfile
from users.models import User

def test_dashboard_logic():
    try:
        user = User.objects.get(username='adminVijaya')
        print(f'Testing dashboard logic for user: {user.username}')
        
        # Test the exact logic from dashboard_redirect
        print('\n=== Testing Lab Profile Check ===')
        lab_profile = LabProfile.objects.filter(user=user).first()
        if lab_profile:
            print(f'Found direct lab profile: {lab_profile.name}')
            if lab_profile.is_approved:
                print('Lab profile is approved - should redirect to lab dashboard')
            else:
                print('Lab profile is not approved')
        else:
            print('No direct lab profile found')
        
        print('\n=== Testing Lab User Check ===')
        from labs.models import LabUser as LabUserModel
        lab_user = LabUserModel.objects.filter(user=user, is_active=True).first()
        if lab_user:
            print(f'Found lab user: {lab_user.lab_profile.name}')
            if lab_user.lab_profile.is_approved:
                print('Lab is approved - should redirect to lab dashboard')
            else:
                print('Lab is not approved')
        else:
            print('No lab user found')
        
        print('\n=== Testing Import ===')
        try:
            from labs.models import LabUser as LabUserModel
            print('LabUser import successful')
        except ImportError as e:
            print(f'LabUser import failed: {e}')
        
    except User.DoesNotExist:
        print('User adminVijaya not found')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    test_dashboard_logic() 