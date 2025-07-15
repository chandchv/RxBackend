from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix database sequences to prevent primary key conflicts'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Fix ExternalLabTestOffering sequence
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('labs_externallabtestoffering', 'id'), 
                    COALESCE(MAX(id), 1)
                ) FROM labs_externallabtestoffering;
            """)
            
            # Fix TestDefinition sequence
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('labs_testdefinition', 'id'), 
                    COALESCE(MAX(id), 1)
                ) FROM labs_testdefinition;
            """)
            
            self.stdout.write(
                self.style.SUCCESS('Successfully fixed database sequences')
            ) 