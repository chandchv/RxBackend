from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Appointment
from scheduling.models import ScheduledAppointment, AppointmentType
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Migrate existing appointments to the unified appointment system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode to see what would be migrated',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY-RUN mode. No changes will be made.'))
        
        # Get all appointments from users app that don't have scheduling info
        appointments_without_scheduling = Appointment.objects.exclude(
            id__in=ScheduledAppointment.objects.values_list('appointment_id', flat=True)
        )
        
        self.stdout.write(f'Found {appointments_without_scheduling.count()} appointments without scheduling info')
        
        # Create default appointment type if it doesn't exist
        default_type, created = AppointmentType.objects.get_or_create(
            name='General Consultation',
            defaults={
                'duration': 30,
                'color': '#007bff',
                'description': 'Default appointment type for existing appointments',
                'is_active': True
            }
        )
        
        if created and not dry_run:
            self.stdout.write(self.style.SUCCESS('Created default appointment type: General Consultation'))
        elif created:
            self.stdout.write(self.style.WARNING('Would create default appointment type: General Consultation'))
        
        migrated_count = 0
        errors = []
        
        with transaction.atomic():
            for appointment in appointments_without_scheduling:
                try:
                    if not dry_run:
                        ScheduledAppointment.objects.create(
                            appointment=appointment,
                            appointment_type=default_type,
                            is_telemedicine=False,
                            is_emergency=False,
                            is_walk_in=getattr(appointment, 'is_walk_in', False),
                            notes=f'Migrated from existing appointment system on {appointment.created_at or "unknown date"}',
                            created_by=None,  # We don't know who created the original appointment
                        )
                    migrated_count += 1
                    
                    if migrated_count % 100 == 0:
                        self.stdout.write(f'Processed {migrated_count} appointments...')
                        
                except Exception as e:
                    error_msg = f'Error migrating appointment {appointment.id}: {str(e)}'
                    errors.append(error_msg)
                    self.stdout.write(self.style.ERROR(error_msg))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would migrate {migrated_count} appointments'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully migrated {migrated_count} appointments'))
        
        if errors:
            self.stdout.write(self.style.ERROR(f'Encountered {len(errors)} errors:'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        
        # Summary
        total_appointments = Appointment.objects.count()
        total_with_scheduling = ScheduledAppointment.objects.count()
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('MIGRATION SUMMARY:')
        self.stdout.write(f'Total appointments in system: {total_appointments}')
        if not dry_run:
            self.stdout.write(f'Appointments with scheduling info: {total_with_scheduling}')
            self.stdout.write(f'Appointments without scheduling info: {total_appointments - total_with_scheduling}')
        else:
            self.stdout.write(f'Appointments that would have scheduling info: {total_with_scheduling + migrated_count}')
        self.stdout.write('='*50) 