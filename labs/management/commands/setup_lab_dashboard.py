from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from labs.models import (
    LabProfile, SpecimenContainer, Specimen, SpecimenProcessing,
    QualityControlTest, QCResult, LabReport, TestResult,
    ReportDelivery, CommunicationLog, B2BPartner, B2BInvoice,
    LabOrder, LabOrderTest, TestDefinition
)
from users.models import Patient, Doctor
from datetime import timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Set up sample data for enhanced lab dashboard'

    def handle(self, *args, **options):
        self.stdout.write('Setting up sample data for lab dashboard...')
        
        # Get or create a lab profile
        try:
            lab_profile = LabProfile.objects.first()
            if not lab_profile:
                self.stdout.write('No lab profile found. Please create a lab profile first.')
                return
        except LabProfile.DoesNotExist:
            self.stdout.write('No lab profile found. Please create a lab profile first.')
            return
        
        # Create specimen containers
        self.stdout.write('Creating specimen containers...')
        container_types = ['VACUTAINER_RED', 'VACUTAINER_PURPLE', 'VACUTAINER_BLUE', 'VACUTAINER_GREEN']
        for i in range(20):
            SpecimenContainer.objects.get_or_create(
                barcode=f"CONTAINER{i+1:03d}",
                defaults={
                    'container_type': random.choice(container_types),
                    'lab_profile': lab_profile,
                    'is_available': random.choice([True, False])
                }
            )
        
        # Create specimen containers
        self.stdout.write('Creating specimens...')
        specimen_types = ['BLOOD', 'URINE', 'STOOL', 'SWAB']
        collection_methods = ['VENIPUNCTURE', 'FINGER_STICK', 'MIDSTREAM', 'SWAB']
        
        # Get some lab orders
        lab_orders = LabOrder.objects.filter(chosen_lab=lab_profile)[:10]
        
        for i, order in enumerate(lab_orders):
            container = SpecimenContainer.objects.filter(is_available=True).first()
            if container:
                specimen = Specimen.objects.get_or_create(
                    specimen_id=f"SP{order.id}-{i+1:03d}",
                    defaults={
                        'container': container,
                        'lab_order': order,
                        'specimen_type': random.choice(specimen_types),
                        'collection_method': random.choice(collection_methods),
                        'collection_date': timezone.now() - timedelta(hours=random.randint(1, 48)),
                        'processing_priority': random.choice(['ROUTINE', 'URGENT', 'STAT', 'EMERGENCY'])
                    }
                )[0]
                
                # Create specimen processing
                SpecimenProcessing.objects.get_or_create(
                    specimen=specimen,
                    defaults={
                        'received_at_lab': specimen.collection_date + timedelta(hours=1),
                        'processing_started': specimen.collection_date + timedelta(hours=2),
                        'processing_completed': specimen.collection_date + timedelta(hours=4) if random.choice([True, False]) else None,
                        'quality_check_passed': random.choice([True, False, None])
                    }
                )
        
        # Create quality control tests
        self.stdout.write('Creating quality control tests...')
        test_definitions = TestDefinition.objects.all()[:5]
        for test_def in test_definitions:
            qc_test = QualityControlTest.objects.get_or_create(
                name=f"QC {test_def.name}",
                defaults={
                    'test_definition': test_def,
                    'qc_type': random.choice(['INTERNAL', 'EXTERNAL', 'PROFICIENCY']),
                    'frequency': random.choice(['Daily', 'Weekly', 'Monthly']),
                    'target_value': random.uniform(10, 100),
                    'acceptable_range_min': random.uniform(8, 90),
                    'acceptable_range_max': random.uniform(12, 110),
                    'is_active': True
                }
            )[0]
            
            # Create QC results
            specimens = Specimen.objects.all()[:5]
            for specimen in specimens:
                QCResult.objects.get_or_create(
                    qc_test=qc_test,
                    specimen=specimen,
                    defaults={
                        'result_value': random.uniform(8, 120),
                        'run_date': timezone.now() - timedelta(hours=random.randint(1, 24)),
                        'is_in_control': random.choice([True, False]),
                        'instrument': random.choice(['Analyzer A', 'Analyzer B', 'Analyzer C']),
                        'lot_number': f"LOT{random.randint(1000, 9999)}"
                    }
                )
        
        # Create lab reports
        self.stdout.write('Creating lab reports...')
        for order in lab_orders[:5]:
            report = LabReport.objects.get_or_create(
                lab_order=order,
                defaults={
                    'report_number': f"RPT{order.id}-{timezone.now().strftime('%Y%m%d%H%M')}",
                    'status': random.choice(['DRAFT', 'PENDING_REVIEW', 'APPROVED', 'RELEASED']),
                    'created_by': lab_profile.user
                }
            )[0]
            
            # Add test results
            specimens = Specimen.objects.filter(lab_order=order)[:3]
            for specimen in specimens:
                test_def = TestDefinition.objects.first()
                if test_def:
                    TestResult.objects.get_or_create(
                        report=report,
                        test_definition=test_def,
                        specimen=specimen,
                        defaults={
                            'result_value': str(random.uniform(10, 100)),
                            'unit': random.choice(['mg/dL', 'mmol/L', 'g/dL', 'U/L']),
                            'reference_range': f"{random.randint(8, 15)}-{random.randint(20, 30)}",
                            'is_abnormal': random.choice([True, False]),
                            'performed_by': lab_profile.user,
                            'performed_at': timezone.now() - timedelta(hours=random.randint(1, 12))
                        }
                    )
        
        # Create B2B partners
        self.stdout.write('Creating B2B partners...')
        partner_types = ['REFERENCE_LAB', 'HOSPITAL', 'CLINIC', 'INSURANCE', 'CORPORATE']
        partner_names = ['City Hospital', 'Regional Lab', 'Corporate Health', 'Insurance Co', 'Medical Center']
        
        for i, name in enumerate(partner_names):
            partner = B2BPartner.objects.get_or_create(
                name=name,
                defaults={
                    'partner_type': partner_types[i % len(partner_types)],
                    'contact_person': f"Contact {i+1}",
                    'email': f"contact{i+1}@{name.lower().replace(' ', '')}.com",
                    'phone': f"+91{random.randint(9000000000, 9999999999)}",
                    'address': f"Address {i+1}, City, State",
                    'credit_days': random.choice([15, 30, 45, 60]),
                    'discount_percentage': random.uniform(0, 15),
                    'is_active': True
                }
            )[0]
            
            # Create invoices
            if random.choice([True, False]):
                B2BInvoice.objects.get_or_create(
                    invoice_number=f"INV{partner.id}-{timezone.now().strftime('%Y%m%d')}-{i+1:03d}",
                    defaults={
                        'partner': partner,
                        'lab_profile': lab_profile,
                        'invoice_date': timezone.now().date() - timedelta(days=random.randint(1, 30)),
                        'due_date': timezone.now().date() + timedelta(days=partner.credit_days),
                        'subtotal': random.uniform(1000, 10000),
                        'discount_amount': random.uniform(0, 500),
                        'tax_amount': random.uniform(0, 200),
                        'total_amount': random.uniform(1000, 10000),
                        'status': random.choice(['DRAFT', 'SENT', 'PAID', 'OVERDUE'])
                    }
                )
        
        # Create communication logs
        self.stdout.write('Creating communication logs...')
        communication_types = ['ORDER_CONFIRMATION', 'PAYMENT_REMINDER', 'COLLECTION_REMINDER', 'RESULT_READY']
        delivery_methods = ['EMAIL', 'SMS', 'WHATSAPP', 'PORTAL']
        
        patients = Patient.objects.all()[:5]
        for patient in patients:
            CommunicationLog.objects.get_or_create(
                lab_profile=lab_profile,
                recipient=patient.user,
                communication_type=random.choice(communication_types),
                defaults={
                    'subject': f"Communication {random.randint(1, 100)}",
                    'message': f"This is a sample communication message {random.randint(1, 100)}",
                    'delivery_method': random.choice(delivery_methods),
                    'status': random.choice(['PENDING', 'SENT', 'DELIVERED']),
                    'related_order': LabOrder.objects.filter(patient=patient).first()
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully set up sample data for lab dashboard!'))
        self.stdout.write(f'Created data for lab: {lab_profile.name}') 