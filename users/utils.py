from django.core.mail import send_mail

def send_status_update_notification(appointment):
    """Send notification about appointment status update"""
    subject = f'Appointment Status Update'
    message = f'Your appointment with Dr. {appointment.doctor.user.get_full_name()} '
    message += f'on {appointment.appointment_date} at {appointment.appointment_time} '
    message += f'has been marked as {appointment.get_status_display()}'
    
    # Send email to patient
    send_mail(
        subject=subject,
        message=message,
        from_email='your@email.com',
        recipient_list=[appointment.patient.user.email],
        fail_silently=True
    )
    
    # Send SMS if phone number exists
    if appointment.patient.phone:
        try:
            send_sms(
                to=appointment.patient.phone,
                message=message
            )
        except Exception as e:
            print(f"Error sending SMS: {str(e)}") 

def send_appointment_update_notification(appointment):
    """Send notification about appointment updates"""
    subject = 'Appointment Update'
    message = f'Your appointment with Dr. {appointment.doctor.user.get_full_name()} '
    message += f'has been rescheduled to {appointment.appointment_date} at {appointment.appointment_time}.'
    
    # Send email
    send_mail(
        subject=subject,
        message=message,
        from_email='your@email.com',
        recipient_list=[appointment.patient.user.email],
        fail_silently=True
    )
    
    # Send SMS if available
    if appointment.patient.phone:
        try:
            send_sms(
                to=appointment.patient.phone,
                message=message
            )
        except Exception as e:
            print(f"Error sending SMS: {str(e)}") 