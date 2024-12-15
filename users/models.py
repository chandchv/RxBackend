from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Clinic(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    registration_number = models.CharField(max_length=50, unique=True)
    logo = models.ImageField(upload_to='clinic_logos/', null=True, blank=True)
    
    def __str__(self):
        return self.name
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)



class Staff(models.Model):
    ROLE_CHOICES = [
        ('RECEPTIONIST', 'Receptionist'),
        ('NURSE', 'Nurse'),
        ('PHARMACIST', 'Pharmacist'),
        ('LAB_TECHNICIAN', 'Lab Technician'),
        ('OTHER', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    clinic = models.ForeignKey(
        Clinic, 
        on_delete=models.CASCADE,
        null=True,  # Allow null temporarily for migration
        blank=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    joining_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    clinic = models.ForeignKey(
        Clinic, 
        on_delete=models.CASCADE, 
        null=True,  # Allow null temporarily for migration
        blank=True
    )
    name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=255, blank=True)
    license_number = models.CharField(max_length=50)
    medical_council = models.CharField(max_length=255)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profile_picture = models.ImageField(upload_to='doctor_profiles/', null=True, blank=True)
    verified = models.BooleanField(default=False)
    verification_details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.name}"

    class Meta: 
        ordering = ['name']

class Patient(models.Model):
    patient_id = models.CharField(max_length=11, default='unknown')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    address = models.TextField()
    pincode = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('SCHEDULED', 'Scheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    appointment_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    # Add reason field if needed:
    # reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'users_appointment'

class Prescription(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    medication = models.TextField()
    dosage = models.TextField()
    instructions = models.TextField()

    def __str__(self):
        return f"Prescription for {self.patient.name} by {self.doctor.user.get_full_name()}"
class Meta:
    db_table = 'users_userprofile'