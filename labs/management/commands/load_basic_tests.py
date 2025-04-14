from django.core.management.base import BaseCommand
from labs.models import TestDefinition

class Command(BaseCommand):
    help = 'Loads basic lab tests into the database'

    def handle(self, *args, **options):
        basic_tests = [
            {
                'name': 'Complete Blood Count (CBC)',
                'short_code': 'CBC',
                'description': 'Measures various components of blood including red blood cells, white blood cells, and platelets',
                'category': 'Hematology',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Hemoglobin A1C',
                'short_code': 'HBA1C',
                'description': 'Measures average blood glucose levels over the past 2-3 months',
                'category': 'Diabetes',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Lipid Profile',
                'short_code': 'LIPID',
                'description': 'Measures cholesterol and triglycerides levels',
                'category': 'Cardiac',
                'preparation_instructions': 'Fasting for 12 hours required'
            },
            {
                'name': 'Liver Function Test (LFT)',
                'short_code': 'LFT',
                'description': 'Measures liver enzymes and proteins',
                'category': 'Liver',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Kidney Function Test (KFT)',
                'short_code': 'KFT',
                'description': 'Measures kidney function through various blood tests',
                'category': 'Kidney',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Thyroid Profile',
                'short_code': 'THYROID',
                'description': 'Measures thyroid hormone levels',
                'category': 'Endocrine',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Vitamin D',
                'short_code': 'VITD',
                'description': 'Measures Vitamin D levels in blood',
                'category': 'Vitamins',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Vitamin B12',
                'short_code': 'VITB12',
                'description': 'Measures Vitamin B12 levels in blood',
                'category': 'Vitamins',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Urine Routine Examination',
                'short_code': 'URE',
                'description': 'Basic urine analysis including physical, chemical, and microscopic examination',
                'category': 'Urine',
                'preparation_instructions': 'First morning urine sample preferred'
            },
            {
                'name': 'Blood Sugar (Fasting)',
                'short_code': 'FBS',
                'description': 'Measures blood glucose levels after fasting',
                'category': 'Diabetes',
                'preparation_instructions': 'Fasting for 8-12 hours required'
            },
            {
                'name': 'Blood Sugar (Post Prandial)',
                'short_code': 'PPBS',
                'description': 'Measures blood glucose levels 2 hours after meals',
                'category': 'Diabetes',
                'preparation_instructions': 'Take test 2 hours after meal'
            },
            {
                'name': 'Serum Creatinine',
                'short_code': 'CREAT',
                'description': 'Measures kidney function',
                'category': 'Kidney',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Serum Uric Acid',
                'short_code': 'UA',
                'description': 'Measures uric acid levels in blood',
                'category': 'Kidney',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Serum Calcium',
                'short_code': 'CAL',
                'description': 'Measures calcium levels in blood',
                'category': 'Minerals',
                'preparation_instructions': 'Fasting not required'
            },
            {
                'name': 'Serum Iron',
                'short_code': 'IRON',
                'description': 'Measures iron levels in blood',
                'category': 'Minerals',
                'preparation_instructions': 'Fasting not required'
            }
        ]

        created_count = 0
        for test_data in basic_tests:
            test, created = TestDefinition.objects.get_or_create(
                name=test_data['name'],
                defaults={
                    'short_code': test_data['short_code'],
                    'description': test_data['description'],
                    'category': test_data['category'],
                    'preparation_instructions': test_data['preparation_instructions']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created test: {test.name}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {created_count} basic tests')) 