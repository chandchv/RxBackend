from django.core.mail import send_mail
from django.conf import settings

def send_appointment_update_notification(appointment):
    """
    Send email notification when an appointment is updated
    """
    try:
        subject = 'Appointment Update Notification'
        message = f"""
        Dear {appointment.patient.get_full_name()},

        Your appointment with Dr. {appointment.doctor.name} has been updated.

        New Details:
        Date: {appointment.appointment_date}
        Time: {appointment.appointment_time}
        
        If you have any questions, please contact the clinic.

        Best regards,
        {appointment.doctor.clinic.name}
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [appointment.patient.email],
            fail_silently=True,
        )
        
    except Exception as e:
        print(f"Error sending notification email: {str(e)}")
        # Don't raise the exception - we don't want to break the appointment update
        # if email fails
        pass

def send_status_update_notification(appointment):
    """
    Send email notification when appointment status changes
    """
    try:
        subject = 'Appointment Status Update'
        message = f"""
        Dear {appointment.patient.get_full_name()},

        Your appointment with Dr. {appointment.doctor.name} has been marked as {appointment.get_status_display()}.

        Appointment Details:
        Date: {appointment.appointment_date}
        Time: {appointment.appointment_time}
        Status: {appointment.get_status_display()}
        
        If you have any questions, please contact the clinic.

        Best regards,
        {appointment.doctor.clinic.name}
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [appointment.patient.email],
            fail_silently=True,
        )
        
    except Exception as e:
        print(f"Error sending status update email: {str(e)}")
        pass 