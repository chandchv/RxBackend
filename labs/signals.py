from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import LabProfile, LabResult, LabOrder, CommissionRule, CommissionLedger
from django.db.models import Sum, Q
from notifications.utils import create_notification

@receiver(post_save, sender=LabProfile)
def send_lab_registration_notifications(sender, instance, created, **kwargs):
    if created:
        # Send notification to admin
        admin_email = getattr(settings, 'ADMIN_EMAIL', None)
        if admin_email:
            certifications = instance.certifications
            if not certifications:
                certifications = "No certifications provided"
            else:
                certifications = ", ".join(certifications)
                
            send_mail(
                'New Lab Registration',
                f'A new lab has registered: {instance.name}\n\n'
                f'Registration Number: {instance.registration_number}\n'
                f'Contact Person: {instance.contact_person} ({instance.contact_person_designation})\n'
                f'Email: {instance.email}\n'
                f'Phone: {instance.phone_number}\n'
                f'Address: {instance.address}\n'
                f'Certifications: {certifications}',
                settings.DEFAULT_FROM_EMAIL,
                [admin_email],
                fail_silently=True,
            )
        
        # Send welcome email to lab
        send_mail(
            'Welcome to RxDoctor',
            'Thank you for registering with RxDoctor. Your account is pending approval.\n\n'
            'We will notify you once your account is approved.',
            settings.DEFAULT_FROM_EMAIL,
            [instance.email],
            fail_silently=True,
        )
    elif instance.is_approved and not instance._state.adding:
        # Send approval email to lab
        send_mail(
            'Lab Registration Approved',
            f'Congratulations! Your lab "{instance.name}" has been approved.\n\n'
            f'You can now log in to your account and start using RxDoctor.\n\n'
            f'Best regards,\nThe RxDoctor Team',
            settings.DEFAULT_FROM_EMAIL,
            [instance.email],
            fail_silently=False,
        )

@receiver(post_save, sender=LabResult)
def notify_doctor_on_result_upload(sender, instance, created, **kwargs):
    """
    Signal receiver to notify the doctor when a lab result is uploaded.
    """
    if created or instance.result_file: # Trigger if created or file is added/changed
        order = instance.order
        doctor_user = order.doctor.user if order.doctor else None
        patient_user = order.patient.user
        lab_user = instance.uploaded_by_user # User who uploaded
        
        if doctor_user:
            # Notify Doctor
            try:
                create_notification(
                    recipient=doctor_user,
                    sender=lab_user, # The lab user who uploaded
                    message=f"Lab results for order #{order.id} ({order.patient.get_full_name()}) have been uploaded by {instance.uploaded_by_lab.name}.",
                    notification_type='lab_result_doctor',
                    related_object=instance # Link to the LabResult object
                )
                print(f"Notification sent to Dr. {doctor_user.username} for result {instance.id}")
            except Exception as e:
                 print(f"Error sending doctor notification for LabResult {instance.id}: {e}")

        # Notify Patient (Optional - uncomment if needed)
        # try:
        #     create_notification(
        #         recipient=patient_user,
        #         sender=lab_user, # The lab user who uploaded
        #         message=f"Your lab results for order #{order.id} are available.",
        #         notification_type='lab_result_patient',
        #         related_object=instance # Link to the LabResult object
        #     )
        #     print(f"Notification sent to Patient {patient_user.username} for result {instance.id}")
        # except Exception as e:
        #         print(f"Error sending patient notification for LabResult {instance.id}: {e}")

@receiver(post_save, sender=LabOrder)
def record_commission_on_result(sender, instance, created, **kwargs):
    """
    Calculate and record commissions when a lab order status changes to RESULT_UPLOADED.
    """
    # Only proceed if status is RESULT_UPLOADED and this is an update
    if not created and instance.status == 'RESULT_UPLOADED':
        # Check if commission has already been recorded
        if CommissionLedger.objects.filter(order=instance).exists():
            return
            
        # Get the chosen lab and doctor
        chosen_lab = instance.chosen_lab
        doctor = instance.doctor
        
        if not chosen_lab or not doctor or not instance.total_price:
            return
            
        # Find applicable commission rule
        rule = CommissionRule.objects.filter(
            lab=chosen_lab,
            is_active=True
        ).first()
        
        if not rule:
            # Try to get global default rule
            rule = CommissionRule.objects.filter(
                lab__isnull=True,
                is_active=True
            ).first()
            
        if not rule:
            return
            
        try:
            # Calculate doctor's commission
            doctor_amount = instance.total_price * (rule.doctor_percentage / 100)
            
            # Create doctor commission ledger entry
            CommissionLedger.objects.create(
                order=instance,
                user=doctor.user,
                amount=doctor_amount,
                rule_used=rule,
                transaction_type='doctor_commission',
                status='EARNED'
            )
            
            # Calculate and record platform fee
            platform_amount = instance.total_price * (rule.platform_percentage / 100)
            
            # Create platform fee ledger entry
            CommissionLedger.objects.create(
                order=instance,
                user=instance.chosen_lab.user,  # Platform fee goes to lab's account
                amount=platform_amount,
                rule_used=rule,
                transaction_type='platform_fee',
                status='EARNED'
            )
            
        except Exception as e:
            # Log the error but don't raise it to prevent order status update from failing
            print(f"Error recording commission for order {instance.id}: {str(e)}") 