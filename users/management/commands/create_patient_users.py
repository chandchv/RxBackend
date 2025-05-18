from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Patient
from notifications.utils import create_notification
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Create user accounts for patients who do not have one'

    def handle(self, *args, **options):
        # Get all patients without user accounts
        patients = Patient.objects.filter(user__isnull=True)
        self.stdout.write(f"Found {patients.count()} patients without user accounts")

        for patient in patients:
            try:
                # Use email as username if available, otherwise use phone number
                username = patient.email if patient.email else patient.phone_number
                if not username:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping patient {patient.id} ({patient.get_full_name()}) - no email or phone number"
                    ))
                    continue

                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    # Append a number to make it unique
                    base_username = username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1

                # Generate a random password (12 characters with letters and digits)
                temp_password = get_random_string(12)

                # Create user account
                user = User.objects.create_user(
                    username=username,
                    email=patient.email,
                    password=temp_password,
                    first_name=patient.first_name,
                    last_name=patient.last_name
                )

                # Link user to patient
                patient.user = user
                patient.save()

                # Send notification if email is available
                if patient.email:
                    try:
                        create_notification(
                            recipient=user,
                            message=f"Your patient account has been created. Username: {username}, Temporary password: {temp_password}. Please change your password after logging in.",
                            sender=None,
                            notification_type='account_created',
                            action_url='/users/change_password/'
                        )
                        self.stdout.write(self.style.SUCCESS(
                            f"Created user account for {patient.get_full_name()} (Username: {username}) and sent notification"
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f"Created user account for {patient.get_full_name()} but failed to send notification: {e}"
                        ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"Created user account for {patient.get_full_name()} (Username: {username})"
                    ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error creating user account for {patient.get_full_name()}: {e}"
                ))

        self.stdout.write(self.style.SUCCESS("Finished creating user accounts")) 