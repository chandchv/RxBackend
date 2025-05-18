from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix PostgreSQL sequences after SQLite migration'

    def handle(self, *args, **options):
        tables = [
            'users_labtestprescription',
            'users_prescription',
            'users_prescriptionitem',
            'users_labtest',
            'users_patient',
            'users_patientvitals',
            'auth_user',
            'notifications_notification'
        ]

        with connection.cursor() as cursor:
            for table in tables:
                try:
                    # Check if table exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        )
                    """, [table])
                    
                    if not cursor.fetchone()[0]:
                        self.stdout.write(f"Table {table} does not exist, skipping")
                        continue

                    # Get the maximum ID from the table
                    cursor.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}")
                    max_id = cursor.fetchone()[0]

                    # Reset the sequence to the max ID
                    sequence_name = f"{table}_id_seq"
                    cursor.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH {max_id}")
                    
                    self.stdout.write(self.style.SUCCESS(f"Successfully reset sequence for {table} to {max_id}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error resetting sequence for {table}: {e}")) 