#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RxBackend.settings')
django.setup()

from labs.models import LabUser, LabProfile
from users.models import User

def test_adminvijaya():
    try:
        user = User.objects.get(username='adminVijaya')
        print(f'User: {user.username}')
        
        # Check direct lab profile
        lab_profile = LabProfile.objects.filter(user=user).first()
        if lab_profile:
            print(f'Direct LabProfile: {lab_profile.name}, Approved: {lab_profile.is_approved}')
        else:
            print('No direct LabProfile found')
        
        # Check lab user association
        lab_user = LabUser.objects.filter(user=user, is_active=True).first()
        if lab_user:
            print(f'LabUser found: {lab_user.lab_profile.name}, Type: {lab_user.user_type}, Approved: {lab_user.lab_profile.is_approved}')
        else:
            print('No LabUser association found')
        
        # Check if user is in lab group
        is_in_lab_group = user.groups.filter(name='lab').exists()
        print(f'In lab group: {is_in_lab_group}')
        
    except User.DoesNotExist:
        print('User adminVijaya not found')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    test_adminvijaya() 