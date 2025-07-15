import uuid
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files import File
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime, timedelta
from .models import (
    SpecimenContainer, Specimen, QCResult, LabReport, 
    TestResult, ReportDelivery, CommunicationLog, B2BInvoice
)

def generate_barcode():
    """Generate a unique barcode for specimen containers"""
    return str(uuid.uuid4())[:12].upper()

def create_specimen_container(lab_profile, container_type):
    """Create a new specimen container with barcode"""
    barcode_value = generate_barcode()
    container = SpecimenContainer.objects.create(
        barcode=barcode_value,
        container_type=container_type,
        lab_profile=lab_profile,
        is_available=True
    )
    return container

def create_specimen_from_order(lab_order, specimen_type, collection_method, collected_by=None):
    """Create a specimen from a lab order"""
    # Get or create a container
    container = SpecimenContainer.objects.filter(
        lab_profile=lab_order.chosen_lab,
        is_available=True
    ).first()
    
    if not container:
        # Create a new container if none available
        container = create_specimen_container(
            lab_order.chosen_lab, 
            'VACUTAINER_RED' if specimen_type == 'BLOOD' else 'CUSTOM'
        )
    
    specimen_id = f"SP{lab_order.id}-{timezone.now().strftime('%Y%m%d%H%M')}"
    
    specimen = Specimen.objects.create(
        specimen_id=specimen_id,
        container=container,
        lab_order=lab_order,
        specimen_type=specimen_type,
        collection_method=collection_method,
        collection_date=timezone.now(),
        collected_by=collected_by,
        processing_priority='ROUTINE'
    )
    
    # Mark container as used
    container.is_available = False
    container.used_at = timezone.now()
    container.save()
    
    return specimen

def run_quality_control(qc_test, specimen, result_value, run_by, instrument=None, lot_number=None):
    """Run quality control test and check Westgard rules"""
    # Check if result is in control
    is_in_control = True
    westgard_violations = []
    
    if qc_test.acceptable_range_min and qc_test.acceptable_range_max:
        if result_value < qc_test.acceptable_range_min or result_value > qc_test.acceptable_range_max:
            is_in_control = False
            westgard_violations.append('1-2s')
    
    # Create QC result
    qc_result = QCResult.objects.create(
        qc_test=qc_test,
        specimen=specimen,
        result_value=result_value,
        run_date=timezone.now(),
        run_by=run_by,
        instrument=instrument,
        lot_number=lot_number,
        is_in_control=is_in_control,
        westgard_violations=westgard_violations
    )
    
    return qc_result

def create_lab_report(lab_order, created_by):
    """Create a lab report for an order"""
    report_number = f"RPT{lab_order.id}-{timezone.now().strftime('%Y%m%d%H%M')}"
    
    report = LabReport.objects.create(
        lab_order=lab_order,
        report_number=report_number,
        status='DRAFT',
        created_by=created_by
    )
    
    return report

def add_test_result(report, test_definition, specimen, result_value, unit, reference_range, performed_by):
    """Add a test result to a report"""
    # Check if result is abnormal
    is_abnormal = False
    abnormality_type = 'NORMAL'
    
    # Simple logic to check for abnormalities (can be enhanced)
    if reference_range:
        try:
            # Parse reference range (e.g., "10-20" or "<10" or ">20")
            if '-' in reference_range:
                min_val, max_val = map(float, reference_range.split('-'))
                if result_value < min_val:
                    is_abnormal = True
                    abnormality_type = 'LOW'
                elif result_value > max_val:
                    is_abnormal = True
                    abnormality_type = 'HIGH'
            elif reference_range.startswith('<'):
                max_val = float(reference_range[1:])
                if result_value >= max_val:
                    is_abnormal = True
                    abnormality_type = 'HIGH'
            elif reference_range.startswith('>'):
                min_val = float(reference_range[1:])
                if result_value <= min_val:
                    is_abnormal = True
                    abnormality_type = 'LOW'
        except (ValueError, AttributeError):
            pass
    
    test_result = TestResult.objects.create(
        report=report,
        test_definition=test_definition,
        specimen=specimen,
        result_value=str(result_value),
        unit=unit,
        reference_range=reference_range,
        is_abnormal=is_abnormal,
        abnormality_type=abnormality_type,
        performed_by=performed_by,
        performed_at=timezone.now()
    )
    
    return test_result

def send_report_delivery(report, recipient_type, delivery_method, recipient_email=None, recipient_phone=None):
    """Send report delivery notification"""
    delivery = ReportDelivery.objects.create(
        report=report,
        recipient_type=recipient_type,
        delivery_method=delivery_method,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        status='PENDING'
    )
    
    # Here you would integrate with actual delivery services
    # For now, we'll just mark as sent
    delivery.status = 'SENT'
    delivery.sent_at = timezone.now()
    delivery.save()
    
    return delivery

def log_communication(lab_profile, communication_type, recipient, subject, message, delivery_method, related_order=None):
    """Log communication with stakeholders"""
    communication = CommunicationLog.objects.create(
        lab_profile=lab_profile,
        communication_type=communication_type,
        recipient=recipient,
        subject=subject,
        message=message,
        delivery_method=delivery_method,
        related_order=related_order,
        status='PENDING'
    )
    
    # Here you would integrate with actual communication services
    # For now, we'll just mark as sent
    communication.status = 'SENT'
    communication.delivered_at = timezone.now()
    communication.save()
    
    return communication

def create_b2b_invoice(partner, lab_profile, orders, invoice_date=None):
    """Create B2B invoice for partner"""
    if invoice_date is None:
        invoice_date = timezone.now().date()
    
    # Calculate totals
    subtotal = sum(order.total_price for order in orders)
    discount_amount = subtotal * (partner.discount_percentage / 100)
    tax_amount = 0  # Add tax calculation logic if needed
    total_amount = subtotal - discount_amount + tax_amount
    
    # Calculate due date
    due_date = invoice_date + timedelta(days=partner.credit_days)
    
    # Generate invoice number
    invoice_number = f"INV{partner.id}-{invoice_date.strftime('%Y%m%d')}-{timezone.now().strftime('%H%M')}"
    
    invoice = B2BInvoice.objects.create(
        invoice_number=invoice_number,
        partner=partner,
        lab_profile=lab_profile,
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status='DRAFT'
    )
    
    # Add invoice items
    for order in orders:
        for test in order.tests.all():
            B2BInvoiceItem.objects.create(
                invoice=invoice,
                lab_order=order,
                test_name=test.name,
                quantity=1,
                unit_price=test.price,
                total_price=test.price
            )
    
    return invoice

def calculate_turnaround_time(lab_order):
    """Calculate turnaround time for a lab order"""
    if lab_order.status == 'COMPLETED':
        # Find the report
        try:
            report = lab_order.report
            if report.released_at:
                return (report.released_at - lab_order.order_date).total_seconds() / 3600  # hours
        except LabReport.DoesNotExist:
            pass
    
    return None

def get_lab_analytics(lab_profile, start_date=None, end_date=None):
    """Get analytics data for lab dashboard"""
    if start_date is None:
        start_date = timezone.now().date() - timedelta(days=30)
    if end_date is None:
        end_date = timezone.now().date()
    
    analytics = {
        'total_orders': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            order_date__date__range=[start_date, end_date]
        ).count(),
        'completed_orders': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='COMPLETED',
            order_date__date__range=[start_date, end_date]
        ).count(),
        'total_revenue': LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='COMPLETED',
            order_date__date__range=[start_date, end_date]
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'average_turnaround_time': 0,
        'quality_control_passed': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            is_in_control=True,
            run_date__date__range=[start_date, end_date]
        ).count(),
        'quality_control_failed': QCResult.objects.filter(
            qc_test__test_definition__offered_by_external_labs__lab_profile=lab_profile,
            is_in_control=False,
            run_date__date__range=[start_date, end_date]
        ).count(),
    }
    
    # Calculate average turnaround time
    completed_orders = LabOrder.objects.filter(
        chosen_lab=lab_profile,
        status='COMPLETED',
        order_date__date__range=[start_date, end_date]
    )
    
    total_tat = 0
    count = 0
    for order in completed_orders:
        tat = calculate_turnaround_time(order)
        if tat:
            total_tat += tat
            count += 1
    
    if count > 0:
        analytics['average_turnaround_time'] = total_tat / count
    
    return analytics 