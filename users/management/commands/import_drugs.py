from django.core.management.base import BaseCommand
from users.scripts.drug_import import import_drugs_from_csv

class Command(BaseCommand):
    help = 'Import drugs from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(f'Starting import from {csv_file_path}...')
        import_drugs_from_csv(csv_file_path)
        self.stdout.write(self.style.SUCCESS('Successfully imported drugs')) 