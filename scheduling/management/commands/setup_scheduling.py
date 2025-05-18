from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Sets up the scheduling system with existing users'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Setting up the scheduling system...'))
        
        # Run migrations
        self.stdout.write('Running migrations...')
        call_command('migrate')
        
        # Setup permissions for existing user groups
        self.stdout.write('Setting up scheduling permissions...')
        call_command('create_scheduling_users')
        
        # Set up django-appointment configuration if needed
        self.stdout.write('Setting up django-appointment configuration...')
        # Additional setup commands could go here
        
        self.stdout.write(self.style.SUCCESS("""
==========================================================
Scheduling System Setup Complete!

The scheduling system is now ready to use with your 
existing user accounts. 

You can access the scheduling dashboard at: /scheduling/
==========================================================
""")) 