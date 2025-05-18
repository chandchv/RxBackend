from django.core.management.base import BaseCommand
from django.db import connections
from users.models import Prescription, PrescriptionItem, LabTestPrescription, LabTest, Patient, PatientVitals, Doctor
from django.contrib.auth.models import User
from notifications.models import Notification
import sqlite3
from datetime import datetime
from django.utils import timezone

class Command(BaseCommand):
    help = 'Migrate data from SQLite to PostgreSQL'

    def handle(self, *args, **options):
        # Connect to SQLite database
        sqlite_conn = sqlite3.connect('db.sqlite3')
        sqlite_conn.row_factory = sqlite3.Row

        # Tables to migrate in order
        tables = {
            'users_prescription': Prescription,
            'users_prescriptionitem': PrescriptionItem,
            'users_labtestprescription': LabTestPrescription,
            'users_labtest': LabTest,
            'users_patientvitals': PatientVitals,
        }

        try:
            # First, create a mapping of old doctor IDs to new doctor users
            cursor = sqlite_conn.cursor()
            cursor.execute("SELECT id, user_id FROM users_doctor")
            doctor_mapping = {row[0]: row[1] for row in cursor.fetchall()}
            
            for table_name, model_class in tables.items():
                self.stdout.write(f"Migrating {table_name}...")
                
                # Get all records from SQLite
                cursor = sqlite_conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                self.stdout.write(f"Found {len(rows)} records in {table_name}")
                
                # Migrate each record
                for row in rows:
                    try:
                        # Convert row to dictionary
                        data = dict(zip([col[0] for col in cursor.description], row))
                        
                        # Handle foreign keys
                        if 'patient_id' in data:
                            try:
                                patient = Patient.objects.get(id=data['patient_id'])
                                data['patient'] = patient
                            except Patient.DoesNotExist:
                                self.stdout.write(self.style.WARNING(
                                    f"Patient {data['patient_id']} not found, skipping record"
                                ))
                                continue
                        
                        if 'doctor_id' in data:
                            try:
                                # Get the user_id from the doctor mapping
                                user_id = doctor_mapping.get(data['doctor_id'])
                                if user_id:
                                    user = User.objects.get(id=user_id)
                                    if table_name == 'users_labtestprescription':
                                        data['doctor'] = user  # LabTestPrescription expects User
                                    else:
                                        data['doctor'] = Doctor.objects.get(user=user)  # Others expect Doctor
                                else:
                                    self.stdout.write(self.style.WARNING(
                                        f"Doctor mapping not found for ID {data['doctor_id']}, skipping record"
                                    ))
                                    continue
                            except (User.DoesNotExist, Doctor.DoesNotExist) as e:
                                self.stdout.write(self.style.WARNING(
                                    f"Doctor user/profile not found for ID {data['doctor_id']}, skipping record"
                                ))
                                continue

                        if 'prescription_id' in data:
                            try:
                                if table_name == 'users_labtest':
                                    # For LabTest, we need a LabTestPrescription
                                    prescription = LabTestPrescription.objects.get(id=data['prescription_id'])
                                else:
                                    prescription = Prescription.objects.get(id=data['prescription_id'])
                                data['prescription'] = prescription
                            except (Prescription.DoesNotExist, LabTestPrescription.DoesNotExist):
                                self.stdout.write(self.style.WARNING(
                                    f"Prescription {data['prescription_id']} not found, skipping record"
                                ))
                                continue

                        # Handle datetime fields
                        for field in ['created_at', 'updated_at', 'date']:
                            if field in data and data[field]:
                                try:
                                    if isinstance(data[field], str):
                                        data[field] = timezone.make_aware(
                                            datetime.strptime(data[field], '%Y-%m-%d %H:%M:%S.%f')
                                        )
                                except (ValueError, TypeError):
                                    data[field] = timezone.now()

                        # Remove ID to let PostgreSQL auto-generate it
                        data.pop('id', None)
                        
                        # Remove foreign key IDs as we've handled the relations
                        data.pop('patient_id', None)
                        data.pop('doctor_id', None)
                        data.pop('prescription_id', None)
                        
                        # Create the record in PostgreSQL
                        instance = model_class.objects.create(**data)
                        self.stdout.write(self.style.SUCCESS(
                            f"Successfully migrated {table_name} record {instance.id}"
                        ))
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"Error migrating record from {table_name}: {str(e)}"
                        ))
                        continue

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Migration error: {str(e)}"))
        finally:
            sqlite_conn.close()

        self.stdout.write(self.style.SUCCESS("Migration completed")) 