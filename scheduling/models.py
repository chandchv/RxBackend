from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from appointment.models import Appointment as BaseAppointment
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

class ScheduledAppointment(BaseAppointment):
    """Extension of django-appointment's Appointment model"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='scheduled_appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='scheduled_appointments')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True)
    is_telemedicine = models.BooleanField(default=False)
    is_emergency = models.BooleanField(default=False)
    is_walk_in = models.BooleanField(default=False)
    token_number = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ], default='scheduled')
    
    # Integration with django-appointment AppointmentType
    appointment_type_id = models.IntegerField(null=True, blank=True, 
                                          help_text="Reference to django-appointment's AppointmentType model")
    
    # Additional metadata - update related_name to avoid clashes
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduling_created_appointments')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-appointment_date', 'appointment_time']
    
    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.appointment_date} at {self.appointment_time}"
    
    def get_appointment_type(self):
        """Get the AppointmentType object if appointment_type_id is set"""
        if self.appointment_type_id:
            from django.apps import apps
            if apps.is_installed('appointment'):
                try:
                    AppointmentType = apps.get_model('appointment', 'AppointmentType')
                    try:
                        return AppointmentType.objects.get(id=self.appointment_type_id)
                    except AppointmentType.DoesNotExist:
                        pass
                except LookupError:
                    # The model doesn't exist in the installed app
                    pass
        return None
