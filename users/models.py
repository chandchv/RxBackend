from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Q

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
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE)
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
    GENDER_CHOICES = [
       ('M', 'Male'),
       ('F', 'Female'),
       ('O', 'Other'),
    ]
   
    BLOOD_GROUP_CHOICES = [
       ('A+', 'A+'), 
       ('A-', 'A-'),
       ('B+', 'B+'), 
       ('B-', 'B-'),
       ('O+', 'O+'), 
       ('O-', 'O-'),
       ('AB+', 'AB+'), 
       ('AB-', 'AB-'),
    ]
    patient_id = models.CharField(max_length=50, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, default=None, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    clinic = models.ForeignKey(
        'Clinic', 
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if not self.patient_id:
            # Generate patient ID if not provided
            last_patient = Patient.objects.order_by('-id').first()
            last_id = int(last_patient.patient_id[3:]) if last_patient else 0
            self.patient_id = f'PAT{str(last_id + 1).zfill(6)}'
        super().save(*args, **kwargs)

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    appointment_date = models.DateTimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.patient.get_full_name()} with Dr. {self.doctor.name}"

class Prescription(models.Model):
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    vitals = models.OneToOneField('PatientVitals', on_delete=models.SET_NULL, null=True, blank=True, related_name='prescription')
    chief_complaints = models.TextField(null=True, blank=True)
    clinical_findings = models.TextField(null=True, blank=True)
    diagnosis = models.TextField(null=True, blank=True)
    advice = models.TextField(null=True, blank=True)
    date = models.DateField(default=timezone.now)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.patient.get_full_name()} by Dr. {self.doctor.name}"

    
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, related_name='items', on_delete=models.CASCADE)
    medicine = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    #frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    duration_unit = models.CharField(max_length=100, null=True, blank=True)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.medicine} - {self.dosage}"

class Drug(models.Model):

    ##clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE)
   # doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
   # patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    sub_category = models.CharField(max_length=255)
    product_name = models.CharField(max_length=255)
    salt_composition = models.CharField(max_length=255)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_manufactured = models.CharField(max_length=255)
    medicine_desc = models.TextField()
    side_effects = models.TextField()
    drug_interactions = models.JSONField()
    

    def __str__(self):
        return self.product_name
    
    @classmethod
    def search_suggestions(cls, query, limit=10):
        if not query:
            return []
            
        return cls.objects.filter(
            Q(product_name__icontains=query) |
            Q(salt_composition__icontains=query)
        ).values('product_name', 'salt_composition')[:limit]

class Meta:
    db_table = 'users_userprofile'

class PatientVitals(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='vitals')
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # in kg
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # in cm
    bmi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    heart_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    oxygen_saturation = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    blood_pressure = models.CharField(max_length=15, null=True, blank=True)  # Format: "120/80"
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def calculate_bmi(self):
        if self.weight and self.height:
            height_in_meters = self.height / 100
            return round(self.weight / (height_in_meters ** 2), 2)
        return None

    def save(self, *args, **kwargs):
        if self.weight and self.height:
            self.bmi = self.calculate_bmi()
        super().save(*args, **kwargs)