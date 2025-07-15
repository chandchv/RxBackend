from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

# Import models but use strings for related models to avoid circular imports
from .models import (
    Bill, BillItem, Payment, ConsultationBilling, LabTestBilling
)


@receiver(post_save, sender='users.Appointment')
def create_appointment_billing(sender, instance, created, **kwargs):
    """
    Create billing records when an appointment is completed
    """
    # Only create billing for completed appointments that don't have billing yet
    if instance.status == 'completed' and not hasattr(instance, 'consultation_billing'):
        # Avoid circular imports
        from users.models import Doctor
        
        # Get the doctor's consultation fee
        doctor = instance.doctor
        base_fee = doctor.consultation_fee
        
        # Check if it's a follow-up appointment (within 15 days of previous appointment)
        previous_completed_appointment = sender.objects.filter(
            patient=instance.patient,
            doctor=doctor,
            status='completed',
            appointment_date__lt=instance.appointment_date,
            appointment_date__gte=instance.appointment_date - timezone.timedelta(days=15)
        ).first()
        
        is_followup = previous_completed_appointment is not None
        followup_discount = Decimal('0.00')
        
        if is_followup:
            # Apply a 50% discount for follow-up appointments
            followup_discount = base_fee * Decimal('0.5')
        
        # Create the bill first
        bill = Bill.objects.create(
            bill_date=instance.appointment_date,
            due_date=instance.appointment_date,
            bill_type='consultation',
            patient=instance.patient,
            doctor=doctor,
            clinic=doctor.clinic,
            appointment=instance,
            notes=f"Consultation with Dr. {doctor.name} on {instance.appointment_date}"
        )
        
        # Create the consultation billing record
        consultation_billing = ConsultationBilling.objects.create(
            appointment=instance,
            bill=bill,
            base_fee=base_fee,
            discount_percentage=Decimal('0.00'),
            is_followup=is_followup,
            followup_discount=followup_discount
        )
        
        # Add a bill item
        BillItem.objects.create(
            bill=bill,
            item_name=f"Consultation with Dr. {doctor.name}",
            description="Medical consultation",
            quantity=1,
            unit_price=consultation_billing.final_fee
        )
        
        # Calculate totals
        bill.calculate_total()
        bill.save()


@receiver(post_save, sender='labs.LabOrderTest')
def create_lab_test_billing(sender, instance, created, **kwargs):
    """
    Create billing records when a lab test is completed
    """
    # Only create billing for completed lab tests that don't have billing yet
    if instance.status == 'COMPLETED' and not hasattr(instance, 'billing'):
        # Avoid circular imports
        from labs.models import TestDefinition
        
        # Get test details and price
        test_definition = instance.test
        order = instance.order
        patient = order.patient
        
        # Get base price from the order test
        base_price = instance.price
        
        # Check for home collection fee (assuming home collection info is in the order)
        is_home_collection = order.status == 'HOME_COLLECTION' if hasattr(order, 'status') else False
        home_collection_fee = Decimal('100.00') if is_home_collection else Decimal('0.00')
        
        # Get the clinic and doctor
        doctor = order.doctor
        clinic = doctor.clinic if doctor else None
        
        # Create the bill first
        bill = Bill.objects.create(
            bill_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=15),
            bill_type='lab_test',
            patient=patient,
            doctor=doctor,
            clinic=clinic,
            lab_order=order,
            notes=f"Lab test: {test_definition.name}"
        )
        
        # Calculate commission if applicable (for external labs)
        commission_percentage = Decimal('0.00')  # Get from order or lab profile if available
        
        # Create the lab test billing record
        lab_test_billing = LabTestBilling.objects.create(
            lab_test=instance,
            bill=bill,
            base_price=base_price,
            discount_percentage=Decimal('0.00'),
            is_home_collection=is_home_collection,
            home_collection_fee=home_collection_fee,
            commission_percentage=commission_percentage
        )
        
        # Add a bill item
        BillItem.objects.create(
            bill=bill,
            item_name=test_definition.name,
            description=f"Lab test: {test_definition.name}",
            quantity=1,
            unit_price=lab_test_billing.final_price
        )
        
        # If home collection, add that as a separate item
        if is_home_collection:
            BillItem.objects.create(
                bill=bill,
                item_name="Home Collection Fee",
                description="Additional charge for sample collection at home",
                quantity=1,
                unit_price=home_collection_fee
            )
        
        # Calculate totals
        bill.calculate_total()
        bill.save() 