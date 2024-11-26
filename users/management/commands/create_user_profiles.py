from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile

class Command(BaseCommand):
    help = 'Creates UserProfile for users that don\'t have one'

    def handle(self, *args, **kwargs):
        users_without_profile = User.objects.filter(userprofile__isnull=True)
        for user in users_without_profile:
            UserProfile.objects.create(
                user=user,
                title='Dr',  # Default value
                medical_degree='Not Specified',
                license_number='Not Specified',
                state_council='Not Specified',
                phone_number='Not Specified',
                address='Not Specified',
                pincode='000000'
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created profile for user: {user.username}')
            ) 