from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from users.models import Doctor, Patient, Clinic

class AppointmentSchedule(models.Model):
    """Schedule configuration for doctors"""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    day_of_week = models.IntegerField(choices=[
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_start_time = models.TimeField(null=True, blank=True)
    break_end_time = models.TimeField(null=True, blank=True)
    appointment_duration = models.IntegerField(default=15, help_text="Duration in minutes")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['doctor', 'clinic', 'day_of_week']
        ordering = ['day_of_week', 'start_time']
    
    def __str__(self):
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return f"{self.doctor} - {day_names[self.day_of_week]} ({self.start_time} - {self.end_time})"

class Holiday(models.Model):
    """Holidays or off days for clinics or doctors"""
    name = models.CharField(max_length=100)
    date = models.DateField()
    description = models.TextField(blank=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, null=True, blank=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, null=True, blank=True)
    is_clinic_holiday = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        if self.is_clinic_holiday:
            return f"{self.name} - {self.clinic} ({self.date})"
        return f"{self.name} - {self.doctor} ({self.date})"

class AppointmentType(models.Model):
    """Appointment types for categorization"""
    name = models.CharField(max_length=100)
    duration = models.IntegerField(default=30, help_text="Duration in minutes")
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.duration} mins)"

# Pure extension model for existing Appointment
class ScheduledAppointment(models.Model):
    """
    Scheduling extension for existing Appointment model
    This creates a bridge between scheduling system and existing appointments
    """
    # Explicit primary key to avoid migration issues
    id = models.AutoField(primary_key=True)
    
    # Reference to the actual appointment in users app
    appointment = models.OneToOneField(
        'users.Appointment', 
        on_delete=models.CASCADE, null=True, blank=True,
        related_name='scheduling_info', 
    )
    
    # Scheduling-specific fields ONLY (no duplication)
    appointment_type = models.ForeignKey(
        AppointmentType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    is_telemedicine = models.BooleanField(default=False)
    is_emergency = models.BooleanField(default=False)
    is_walk_in = models.BooleanField(default=False)
    
    # Integration with django-appointment (optional)
    django_appointment_id = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Reference to django-appointment's Appointment model if used"
    )
    
    # Scheduling metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='scheduled_appointments_created'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    class Meta:
        ordering = ['-appointment__appointment_date', 'appointment__appointment_time']
    
    def __str__(self):
        return f"Scheduling Info for {self.appointment}"
    
    # Proxy properties to access appointment data easily
    @property
    def patient(self):
        return self.appointment.patient
    
    @property
    def doctor(self):
        return self.appointment.doctor
    
    @property
    def appointment_date(self):
        return self.appointment.appointment_date
    
    @property
    def appointment_time(self):
        return self.appointment.appointment_time
    
    @property
    def status(self):
        return self.appointment.status
    
    @property
    def reason(self):
        return self.appointment.reason
    
    @property
    def clinic(self):
        return self.appointment.doctor.clinic if self.appointment.doctor else None
    
    def get_django_appointment(self):
        """Get the django-appointment object if django_appointment_id is set"""
        if self.django_appointment_id:
            from django.apps import apps
            if apps.is_installed('appointment'):
                try:
                    DjangoAppointment = apps.get_model('appointment', 'Appointment')
                    try:
                        return DjangoAppointment.objects.get(id=self.django_appointment_id)
                    except DjangoAppointment.DoesNotExist:
                        pass
                except LookupError:
                    # The model doesn't exist in the installed app
                    pass
        return None

class SchedulingSettings(models.Model):
    """Global scheduling system settings"""
    # General settings
    default_appointment_duration = models.IntegerField(default=30, help_text="Default duration in minutes")
    min_scheduling_notice = models.IntegerField(default=24, help_text="Minimum hours in advance")
    max_days_in_advance = models.IntegerField(default=90, help_text="Maximum days in advance")
    buffer_between_appointments = models.IntegerField(default=5, help_text="Buffer in minutes")
    
    # Working hours defaults
    default_start_time = models.TimeField(default='09:00')
    default_end_time = models.TimeField(default='17:00')
    
    # Notification settings
    send_confirmation_emails = models.BooleanField(default=True)
    send_reminder_emails = models.BooleanField(default=True)
    reminder_hours = models.IntegerField(default=24, help_text="Hours before appointment")
    send_sms_reminders = models.BooleanField(default=False)
    sms_reminder_hours = models.IntegerField(default=2, help_text="Hours before appointment")
    
    # System metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Scheduling Settings"
        verbose_name_plural = "Scheduling Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one settings instance exists
        if not self.pk and SchedulingSettings.objects.exists():
            raise ValueError("Only one SchedulingSettings instance is allowed")
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the single settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    def __str__(self):
        return "Scheduling System Settings"
