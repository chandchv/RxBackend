from django.core.management.base import BaseCommand
import psycopg2
from django.conf import settings

class Command(BaseCommand):
    help = 'Test PostgreSQL connection directly'

    def handle(self, *args, **kwargs):
        try:
            # Get database settings
            db_settings = settings.DATABASES['default']
            
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                dbname=db_settings['rxdoctor'],
                user=db_settings['postgres'],
                password=db_settings['admin'],
                host=db_settings['localhost'],
                port=db_settings['5432']
            )
            
            # Get server version
            cur = conn.cursor()
            cur.execute('SELECT version();')
            version = cur.fetchone()[0]
            
            self.stdout.write(self.style.SUCCESS(
                f"\nSuccessfully connected to PostgreSQL!"
                f"\n- Version: {version}"
                f"\n- Database: {db_settings['rxdoctor']}"
                f"\n- Host: {db_settings['localhost']}"
                f"\n- Port: {db_settings['5432']}"
            ))
            
            # Close connection
            cur.close()
            conn.close()
            
        except psycopg2.Error as e:
            self.stdout.write(self.style.ERROR(
                f"\nFailed to connect to PostgreSQL:"
                f"\nError: {str(e)}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\nUnexpected error:"
                f"\nError: {str(e)}"
            )) 