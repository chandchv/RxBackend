from django.core.management.base import BaseCommand
from django.core import serializers
from datetime import datetime, date, time
from decimal import Decimal
import json
from users.models import *  # Import your models

class Command(BaseCommand):
    help = 'Export data with proper encoding'

    def value_handler(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.strftime('%H:%M:%S')
        elif isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

    def clean_value(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, time):
            return value.strftime('%H:%M:%S')
        elif isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, str):
            return value.encode('utf-8').decode('utf-8')
        return value

    def handle(self, *args, **kwargs):
        try:
            # Dictionary to store all data
            all_data = []
            
            # Models to export (in order of dependencies)
            models_to_export = [
                User,
                Doctor,
                Patient,
                Appointment,
                Prescription,
                PrescriptionItem,
                PatientVitals,
                Clinic,
                ClinicAdministrator,
                UserProfile,
                Drug,
                ClinicAdmin,
                DoctorAvailability,
                AppointmentSlot,
                ActivityLog,
                DoctorLeave,
                Billing,
                Staff,
                BillingItem,
                Bill,
                BillingItem,
                Payment
            ]

            for model in models_to_export:
                self.stdout.write(f'Exporting {model.__name__}...')
                try:
                    # Get all objects for the current model
                    objects = model.objects.all()
                    
                    if not objects.exists():
                        self.stdout.write(f'No data found for {model.__name__}')
                        continue
                    
                    # Serialize the objects
                    serialized_data = serializers.serialize('python', objects)
                    
                    for item in serialized_data:
                        try:
                            # Clean the data
                            clean_item = {
                                'model': item['model'],
                                'pk': item['pk'],
                                'fields': {}
                            }
                            
                            # Clean fields
                            for field, value in item['fields'].items():
                                if value is not None:
                                    try:
                                        clean_item['fields'][field] = self.clean_value(value)
                                    except Exception as e:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Error cleaning field {field} in {model.__name__}: {str(e)}'
                                            )
                                        )
                            
                            all_data.append(clean_item)
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Error processing item in {model.__name__}: {str(e)}'
                                )
                            )
                            continue
                            
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing {model.__name__}: {str(e)}')
                    )
                    continue

            if not all_data:
                self.stdout.write(self.style.WARNING('No data was exported!'))
                return

            # Write to file with proper encoding and type handling
            with open('clean_data.json', 'w', encoding='utf-8') as f:
                json.dump(
                    all_data, 
                    f, 
                    ensure_ascii=False, 
                    indent=2,
                    default=self.value_handler
                )

            self.stdout.write(self.style.SUCCESS(
                f'Successfully exported {len(all_data)} objects to clean_data.json'
            ))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Export failed: {str(e)}')
            ) 