from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=10, null=True, blank=True)
    medical_degree = models.CharField(max_length=100, null=True, blank=True)
    license_number = models.CharField(max_length=50, null=True, blank=True)
    state_council = models.CharField(max_length=100, null=True, blank=True)
    clinic_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    year_of_registration = models.CharField(max_length=4, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'userprofile'):
        UserProfile.objects.create(user=instance)

class Patient(models.Model):
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
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.CharField(max_length=100)
    appointment_date = models.DateTimeField()
    symptoms = models.TextField()
    diagnosis = models.TextField()
    medications = models.TextField()

    def __str__(self):
        return f"Appointment for {self.patient} with {self.doctor} on {self.appointment_date}"
