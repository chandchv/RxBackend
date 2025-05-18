import decimal
import uuid
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from decimal import Decimal
from django.core.exceptions import ValidationError

from .models import (
    Bill, BillItem, Payment, BillingItem, 
    LabTestBilling, ConsultationBilling, InsuranceClaim
)

# Payment Integration placeholder - would be replaced with actual payment gateway
# like Stripe, Razorpay, etc.
class PaymentGateway:
    @staticmethod
    def create_payment_intent(amount, currency='INR', metadata=None):
        """
        Create a payment intent in the payment gateway
        
        In a real implementation, this would call the payment gateway's API
        """
        # Mock implementation for development
        return {
            'id': f'pi_{uuid.uuid4().hex}',
            'amount': amount,
            'currency': currency,
            'status': 'created',
            'client_secret': f'cs_{uuid.uuid4().hex}',
            'metadata': metadata or {}
        }
    
    @staticmethod
    def confirm_payment_intent(payment_intent_id):
        """
        Confirm a payment intent in the payment gateway
        
        In a real implementation, this would call the payment gateway's API
        """
        # Mock implementation for development
        return {
            'id': payment_intent_id,
            'status': 'succeeded'
        }


def initiate_appointment_payment(appointment):
    """
    Initialize payment for an appointment
    
    Args:
        appointment: The appointment object
        
    Returns:
        dict: Payment intent details
    """
    # Calculate fee
    doctor = appointment.doctor
    fee = doctor.consultation_fee if hasattr(doctor, 'consultation_fee') else Decimal('500.00')
    
    # Check if it's a follow-up appointment
    is_followup = False
    previous_completed_appointment = appointment.__class__.objects.filter(
        patient=appointment.patient,
        doctor=doctor,
        status='completed',
        appointment_date__lt=appointment.appointment_date,
        appointment_date__gte=appointment.appointment_date - timezone.timedelta(days=15)
    ).first()
    
    if previous_completed_appointment:
        is_followup = True
        fee = fee * Decimal('0.5')  # 50% discount for follow-up
    
    # Create payment intent
    metadata = {
        'appointment_id': appointment.id,
        'patient_id': appointment.patient.id,
        'doctor_id': doctor.id,
        'type': 'appointment_prepayment'
    }
    
    payment_intent = PaymentGateway.create_payment_intent(
        amount=int(fee * 100),  # Convert to smallest currency unit (paise)
        metadata=metadata
    )
    
    # Update appointment with payment intent ID
    appointment.payment_intent_id = payment_intent['id']
    appointment.save(update_fields=['payment_intent_id'])
    
    return {
        'payment_intent': payment_intent,
        'amount': fee,
        'is_followup': is_followup
    }


def confirm_appointment_payment(appointment, payment_intent_id):
    """
    Confirm payment for an appointment
    
    Args:
        appointment: The appointment object
        payment_intent_id: The payment intent ID from the payment gateway
        
    Returns:
        bool: Whether the payment was confirmed successfully
    """
    if appointment.payment_intent_id != payment_intent_id:
        raise ValidationError("Payment intent ID does not match")
    
    # In a real implementation, we would verify the payment status with the payment gateway
    payment_status = PaymentGateway.confirm_payment_intent(payment_intent_id)
    
    if payment_status['status'] == 'succeeded':
        # Update appointment with prepaid amount
        doctor = appointment.doctor
        fee = doctor.consultation_fee if hasattr(doctor, 'consultation_fee') else Decimal('500.00')
        
        # Apply follow-up discount if applicable
        is_followup = False
        previous_completed_appointment = appointment.__class__.objects.filter(
            patient=appointment.patient,
            doctor=doctor,
            status='completed',
            appointment_date__lt=appointment.appointment_date,
            appointment_date__gte=appointment.appointment_date - timezone.timedelta(days=15)
        ).first()
        
        if previous_completed_appointment:
            is_followup = True
            fee = fee * Decimal('0.5')  # 50% discount for follow-up
        
        appointment.prepaid_amount = fee
        appointment.save(update_fields=['prepaid_amount'])
        return True
    
    return False


@transaction.atomic
def generate_provisional_invoice(appointment):
    """
    Generate a provisional invoice for an appointment
    
    Args:
        appointment: The appointment object
        
    Returns:
        Bill: The generated bill
    """
    patient = appointment.patient
    doctor = appointment.doctor
    clinic = doctor.clinic
    
    # Create a new bill
    bill = Bill.objects.create(
        patient=patient,
        doctor=doctor,
        clinic=clinic,
        appointment=appointment,
        bill_date=timezone.now().date(),
        due_date=timezone.now().date() + timezone.timedelta(days=15),
        bill_type='consultation',
        status='pending',
        notes=f"Consultation with Dr. {doctor.name} on {appointment.appointment_date}"
    )
    
    # Calculate base fee
    base_fee = doctor.consultation_fee if hasattr(doctor, 'consultation_fee') else Decimal('500.00')
    
    # Check if it's a follow-up visit
    is_followup = False
    followup_discount = Decimal('0.00')
    previous_completed_appointment = appointment.__class__.objects.filter(
        patient=patient,
        doctor=doctor,
        status='completed',
        appointment_date__lt=appointment.appointment_date,
        appointment_date__gte=appointment.appointment_date - timezone.timedelta(days=15)
    ).first()
    
    if previous_completed_appointment:
        is_followup = True
        followup_discount = base_fee * Decimal('0.5')  # 50% discount
    
    # Create consultation billing record
    consultation_billing = ConsultationBilling.objects.create(
        appointment=appointment,
        bill=bill,
        base_fee=base_fee,
        discount_percentage=Decimal('0.00'),
        is_followup=is_followup,
        followup_discount=followup_discount
    )
    
    # Add consultation as a bill item
    BillItem.objects.create(
        bill=bill,
        item_name=f"Consultation with Dr. {doctor.name}",
        description="Medical consultation",
        quantity=1,
        unit_price=consultation_billing.final_fee
    )
    
    # Add prescribed medications and procedures if any
    # This would require additional models and data that may not be in the current codebase
    
    # Calculate total
    bill.calculate_total()
    bill.save()
    
    # If appointment has prepaid amount, create a payment record
    if appointment.prepaid_amount and appointment.prepaid_amount > 0:
        Payment.objects.create(
            bill=bill,
            amount=appointment.prepaid_amount,
            payment_date=timezone.now().date(),
            payment_method='online',  # Assuming online prepayment
            transaction_id=appointment.payment_intent_id or '',
            notes="Prepaid appointment fee",
            receipt_number=None  # Will be auto-generated on save
        )
        
        # Update bill status based on payment
        bill.update_status()
        bill.save()
    
    return bill


@transaction.atomic
def finalize_invoice(invoice, added_items=None):
    """
    Finalize an invoice by adding additional items and updating status
    
    Args:
        invoice: The invoice (Bill) object
        added_items: Additional items to add to the invoice [{'name', 'description', 'quantity', 'price'}, ...]
        
    Returns:
        dict: Updated invoice details and payment information if needed
    """
    # Add additional items if provided
    if added_items:
        for item in added_items:
            BillItem.objects.create(
                bill=invoice,
                item_name=item['name'],
                description=item.get('description', ''),
                quantity=item.get('quantity', 1),
                unit_price=item['price']
            )
    
    # Recalculate totals
    invoice.calculate_total()
    
    # Change status to finalized
    invoice.status = 'finalized'
    invoice.save()
    
    # Calculate if payment is needed
    total_paid = sum(payment.amount for payment in invoice.payments.all())
    balance_due = invoice.total - total_paid
    
    payment_intent = None
    if balance_due > 0:
        # Create a payment intent for the balance
        metadata = {
            'bill_id': invoice.id,
            'patient_id': invoice.patient.id,
            'doctor_id': invoice.doctor.id if invoice.doctor else None,
            'type': 'invoice_payment'
        }
        
        payment_intent = PaymentGateway.create_payment_intent(
            amount=int(balance_due * 100),  # Convert to smallest currency unit
            metadata=metadata
        )
    
    return {
        'invoice': invoice,
        'balance_due': balance_due,
        'payment_intent': payment_intent
    }


def record_invoice_payment(invoice, payment_intent_id, amount=None, payment_method='online'):
    """
    Record a payment for an invoice
    
    Args:
        invoice: The invoice (Bill) object
        payment_intent_id: Payment intent ID from payment gateway
        amount: Payment amount (if None, uses the invoice total)
        payment_method: Method of payment
        
    Returns:
        Payment: The payment record
    """
    # Verify payment with gateway (in a real implementation)
    payment_status = PaymentGateway.confirm_payment_intent(payment_intent_id)
    
    if payment_status['status'] != 'succeeded':
        raise ValidationError("Payment verification failed")
    
    # Determine payment amount
    if amount is None:
        total_paid = sum(payment.amount for payment in invoice.payments.all())
        amount = invoice.total - total_paid
    
    # Create payment record
    payment = Payment.objects.create(
        bill=invoice,
        amount=amount,
        payment_date=timezone.now().date(),
        payment_method=payment_method,
        transaction_id=payment_intent_id,
        notes="Online payment"
    )
    
    # Update invoice status
    invoice.update_status()
    invoice.save()
    
    return payment


def generate_invoice_pdf(invoice):
    """
    Generate a PDF for an invoice
    
    Args:
        invoice: The invoice (Bill) object
        
    Returns:
        str: Path to the generated PDF file
    """
    # This would typically use a PDF generation library like WeasyPrint or ReportLab
    # For demonstration purposes, we'll return a placeholder
    pdf_path = f"invoices/{invoice.bill_number}.pdf"
    
    # In a real implementation, we would generate the PDF here
    
    return pdf_path 