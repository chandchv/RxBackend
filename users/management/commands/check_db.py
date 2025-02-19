from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
import psycopg2

class Command(BaseCommand):
    help = 'Check PostgreSQL connection status'

    def handle(self, *args, **kwargs):
        try:
            db_conn = connections['default']
            db_conn.cursor()
            
            # Get connection details
            db_settings = db_conn.settings_dict
            
            self.stdout.write(self.style.SUCCESS(
                f"\nDatabase connection successful!"
                f"\n- Engine: {db_settings['ENGINE']}"
                f"\n- Name: {db_settings['NAME']}"
                f"\n- Host: {db_settings['HOST']}"
                f"\n- Port: {db_settings['PORT']}"
                f"\n- User: {db_settings['USER']}"
            ))
            
        except OperationalError as e:
            self.stdout.write(self.style.ERROR(
                f"\nFailed to connect to PostgreSQL:"
                f"\nError: {str(e)}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\nUnexpected error:"
                f"\nError: {str(e)}"
            )) 