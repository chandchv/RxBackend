from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Doctor, Patient, Clinic
from scheduling.models import AppointmentSchedule, Holiday, ScheduledAppointment

class Command(BaseCommand):
    help = 'Setup scheduling permissions for existing user groups'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Setting up scheduling permissions for existing user groups...'))
        
        # Get or ensure doctor group exists
        doctor_group, created = Group.objects.get_or_create(name='Doctors')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Doctors group'))
        else:
            self.stdout.write(self.style.SUCCESS('Using existing Doctors group'))
            
        # Get or ensure staff group exists
        staff_group, created = Group.objects.get_or_create(name='Staff')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Staff group'))
        else:
            self.stdout.write(self.style.SUCCESS('Using existing Staff group'))
        
        # Add permissions to groups
        # Get content types
        appointment_content_type = ContentType.objects.get_for_model(ScheduledAppointment)
        schedule_content_type = ContentType.objects.get_for_model(AppointmentSchedule)
        holiday_content_type = ContentType.objects.get_for_model(Holiday)
        
        # Get permissions
        view_appointment = Permission.objects.get(
            codename='view_scheduledappointment',
            content_type=appointment_content_type
        )
        add_appointment = Permission.objects.get(
            codename='add_scheduledappointment',
            content_type=appointment_content_type
        )
        change_appointment = Permission.objects.get(
            codename='change_scheduledappointment',
            content_type=appointment_content_type
        )
        
        # Add permissions to doctor group
        doctor_group.permissions.add(view_appointment, add_appointment, change_appointment)
        
        # Add more permissions to staff group
        staff_group.permissions.add(
            *Permission.objects.filter(content_type=appointment_content_type),
            *Permission.objects.filter(content_type=schedule_content_type),
            *Permission.objects.filter(content_type=holiday_content_type)
        )
        
        self.stdout.write(self.style.SUCCESS('Scheduling permissions added to existing groups'))
        
        # Display available doctors for login
        doctors = Doctor.objects.all()
        if doctors.exists():
            self.stdout.write(self.style.SUCCESS('\nAvailable doctor accounts:'))
            for doctor in doctors:
                if hasattr(doctor, 'user') and doctor.user:
                    self.stdout.write(f"- {doctor.name} (username: {doctor.user.username})")
        else:
            self.stdout.write(self.style.WARNING('No doctor accounts found'))
            
        # Display available staff users
        staff_users = User.objects.filter(is_staff=True, is_superuser=False)
        if staff_users.exists():
            self.stdout.write(self.style.SUCCESS('\nAvailable staff accounts:'))
            for user in staff_users:
                self.stdout.write(f"- {user.get_full_name() or user.username} (username: {user.username})")
        else:
            self.stdout.write(self.style.WARNING('No staff accounts found'))
            
        # Display superusers
        super_users = User.objects.filter(is_superuser=True)
        if super_users.exists():
            self.stdout.write(self.style.SUCCESS('\nAvailable admin accounts:'))
            for user in super_users:
                self.stdout.write(f"- {user.get_full_name() or user.username} (username: {user.username})")
        else:
            self.stdout.write(self.style.WARNING('No admin accounts found'))
            
        self.stdout.write(self.style.SUCCESS('\nScheduling system ready to use with existing user accounts.')) 