from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model

from elasticsearch_dsl import Q

User = get_user_model()

# Define the phone number regex validator
phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class TimeStampedModel(models.Model):
    """Abstract base class with created and updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True )

    class Meta:
        abstract = True

class Clinic(TimeStampedModel):
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    specializations = models.TextField(blank=True, null=True)
    opening_hours = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=255, blank=True, null=True)
    registration_number = models.CharField(max_length=50, unique=True, db_index=True)
    logo = models.ImageField(upload_to='clinic_logos/', null=True, blank=True)
    clinic_admins = models.ManyToManyField(
        User, 
        related_name='administered_clinics',
        through='ClinicAdministrator'
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['registration_number']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        # Add custom validation if needed
        if self.email and not self.email.endswith(('.com', '.org', '.net')):
            raise ValidationError('Invalid email domain')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Get or create superuser
            superuser = User.objects.filter(is_superuser=True).first()
            if superuser:
                ClinicAdministrator.objects.create(
                    clinic=self,
                    user=superuser,
                    is_primary=True
                )

class ClinicAdministrator(TimeStampedModel):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['clinic', 'user']
        indexes = [
            models.Index(fields=['clinic', 'user']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.clinic.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary admin per clinic
            ClinicAdministrator.objects.filter(
                clinic=self.clinic, 
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)

class UserProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=17, validators=[phone_regex])
    address = models.TextField(null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()}'s profile"

    class Meta:
        db_table = 'users_userprofile'

class Doctor(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor')
    clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE, related_name='doctors')
    name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=255, blank=True)
    date_of_registration = models.DateField(null=True, blank=True)
    license_number = models.CharField(max_length=50, unique=True, db_index=True)
    medical_council = models.CharField(max_length=255)
    consultation_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    profile_picture = models.ImageField(upload_to='doctor_profiles/', null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=17, validators=[phone_regex], null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    verification_details = models.JSONField(null=True, blank=True)
    qualification = models.CharField(max_length=100, null=True, blank=True)
    experience = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['license_number']),
            models.Index(fields=['clinic', 'specialization']),
        ]
        db_table = 'users_doctor'

    def __str__(self):
        return f"Dr. {self.name}"

    def get_upcoming_appointments(self):
        return self.appointments.filter(
            appointment_date__gte=timezone.now().date(),
            status='scheduled'
        ).order_by('appointment_date', 'appointment_time')

class Patient(TimeStampedModel):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    patient_id = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='patient',
        null=True, 
        blank=True
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(
        max_length=3, 
        choices=BLOOD_GROUP_CHOICES, 
        blank=True, 
        null=True
    )
    phone_number = models.CharField(max_length=17, validators=[phone_regex])
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    clinic = models.ForeignKey(
        'Clinic', 
        on_delete=models.CASCADE,
        related_name='patients'
    )
    doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_patients'
    )
    
    # Medical history fields
    existing_diseases = models.TextField(blank=True, help_text="List any existing medical conditions")
    current_medications = models.TextField(blank=True, help_text="List any current medications")
    allergies = models.TextField(blank=True, help_text="List any known allergies")

    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        indexes = [
            models.Index(fields=['patient_id']),
            models.Index(fields=['clinic', 'phone_number']),
        ]

    def __str__(self):
        if self.user:
            return self.user.get_full_name()
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        if self.user:
            return self.user.get_full_name()
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if not self.patient_id:
            last_patient = Patient.objects.order_by('-id').first()
            last_id = int(last_patient.patient_id[3:]) if last_patient else 0
            self.patient_id = f'PAT{str(last_id + 1).zfill(6)}'
        super().save(*args, **kwargs)

    def get_age(self):
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < 
            (self.date_of_birth.month, self.date_of_birth.day)
        )

class Appointment(TimeStampedModel):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    patient = models.ForeignKey(
        'Patient', 
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    doctor = models.ForeignKey(
        'Doctor', 
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='scheduled'
    )

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        indexes = [
            models.Index(fields=['appointment_date', 'status']),
            models.Index(fields=['doctor', 'appointment_date']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.appointment_date}"

    def clean(self):
        if self.appointment_date < timezone.now().date():
            raise ValidationError("Cannot schedule appointments in the past")
        
        # Check for conflicting appointments
        conflicts = Appointment.objects.filter(
            doctor=self.doctor,
            appointment_date=self.appointment_date,
            appointment_time=self.appointment_time,
            status='scheduled'
        ).exclude(id=self.id)
        
        if conflicts.exists():
            raise ValidationError("This time slot is already booked")

class Prescription(TimeStampedModel):
    patient = models.ForeignKey(
        'Patient', 
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    doctor = models.ForeignKey(
        'Doctor', 
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    vitals = models.OneToOneField(
        'PatientVitals', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='prescription'
    )
    chief_complaints = models.TextField(null=True, blank=True)
    clinical_findings = models.TextField(null=True, blank=True)
    diagnosis = models.TextField(null=True, blank=True)
    advice = models.TextField(null=True, blank=True)
    date = models.DateField(default=timezone.now)
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['patient', 'date']),
            models.Index(fields=['doctor', 'date']),
        ]

    def __str__(self):
        return f"Prescription for {self.patient.get_full_name()} by Dr. {self.doctor.name}"

    def clean(self):
        if self.follow_up_date and self.follow_up_date < self.date:
            raise ValidationError("Follow-up date cannot be before prescription date")

class PrescriptionItem(TimeStampedModel):
    prescription = models.ForeignKey(
        Prescription, 
        related_name='items', 
        on_delete=models.CASCADE
    )
    medicine = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    duration_unit = models.CharField(max_length=100, null=True, blank=True)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.medicine} - {self.dosage}"

class Drug(TimeStampedModel):
    sub_category = models.CharField(max_length=255)
    product_name = models.CharField(max_length=255, db_index=True)
    salt_composition = models.CharField(max_length=255)
    product_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    product_manufactured = models.CharField(max_length=255)
    medicine_desc = models.TextField()
    side_effects = models.TextField()
    drug_interactions = models.JSONField()

    class Meta:
        ordering = ['product_name']
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['salt_composition']),
        ]

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

class PatientVitals(TimeStampedModel):
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE, 
        related_name='vitals'
    )
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(300)]
    )
    height = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(300)]
    )
    bmi = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    temperature = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    heart_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)]
    )
    oxygen_saturation = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    blood_pressure = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    recorded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
        ]

    def calculate_bmi(self):
        if self.weight and self.height:
            height_in_meters = self.height / 100
            return round(self.weight / (height_in_meters ** 2), 2)
        return None

    def save(self, *args, **kwargs):
        if self.weight and self.height:
            self.bmi = self.calculate_bmi()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Vitals for {self.patient.get_full_name()} on {self.created_at.date()}"

class ClinicAdmin(TimeStampedModel):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='clinic_admin'
    )
    clinic = models.OneToOneField(
        'Clinic', 
        on_delete=models.CASCADE, 
        related_name='admin'
    )

    class Meta:
        verbose_name = "Clinic Administrator"
        verbose_name_plural = "Clinic Administrators"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['clinic']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.clinic.name}"

    def clean(self):
        if self.user and not self.user.is_staff:
            self.user.is_staff = True
            self.user.save()

class DoctorAvailability(TimeStampedModel):
    SHIFT_CHOICES = [
        ('morning', 'Morning (8 AM - 12 PM)'),
        ('afternoon', 'Afternoon (2 PM - 6 PM)'),
        ('evening', 'Evening (7 PM - 10 PM)'),
    ]
    
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    doctor = models.ForeignKey(
        'Doctor', 
        on_delete=models.CASCADE,
        related_name='availability'
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['doctor', 'day_of_week', 'shift']
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['doctor', 'day_of_week']),
        ]
        
    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
    
    def generate_slots(self, date):
        """Generate 10-minute slots for the given date"""
        if not isinstance(date, datetime):
            date = datetime.combine(date, datetime.min.time())
            
        slots = []
        current_time = datetime.combine(date, self.start_time)
        end_datetime = datetime.combine(date, self.end_time)
        
        while current_time + timedelta(minutes=10) <= end_datetime:
            slots.append(current_time)
            current_time += timedelta(minutes=10)
            
        return slots

    def __str__(self):
        return f"{self.doctor.name} - {self.get_day_of_week_display()} ({self.shift})"

class AppointmentSlot(TimeStampedModel):
    doctor = models.ForeignKey(
        'Doctor', 
        on_delete=models.CASCADE,
        related_name='appointment_slots'
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)
    appointment = models.OneToOneField(
        'Appointment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='slot'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ['doctor', 'date', 'start_time']
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['doctor', 'date', 'is_booked']),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.date} {self.start_time}"

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
        if self.date < timezone.now().date():
            raise ValidationError("Cannot create slots for past dates")

class ActivityLog(TimeStampedModel):
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('login', 'Logged In'),
        ('logout', 'Logged Out'),
    ]
    
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.action} - {self.created_at}"

class DoctorLeave(TimeStampedModel):
    doctor = models.ForeignKey(
        'Doctor', 
        on_delete=models.CASCADE,
        related_name='leaves'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['doctor', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.doctor} - {self.start_date} to {self.end_date}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        if self.start_date < timezone.now().date():
            raise ValidationError("Cannot add leave for past dates")

class Billing(TimeStampedModel):
    patient = models.ForeignKey(
        'Patient', 
        on_delete=models.CASCADE,
        related_name='billings'
    )
    appointment = models.OneToOneField(
        'Appointment', 
        on_delete=models.CASCADE,
        related_name='billing'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['is_paid', '-created_at']),
        ]

    def __str__(self):
        return f"Billing for {self.patient} - {self.appointment}"

    @staticmethod
    def get_free_appointment_eligibility(patient):
        one_month_ago = timezone.now() - timezone.timedelta(days=30)
        return Billing.objects.filter(
            patient=patient,
            is_paid=True,
            created_at__gte=one_month_ago
        ).exists()

class Staff(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    role = models.CharField(max_length=100)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='staff_members')

    class Meta:
        ordering = ['user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """Create or update user profile when user is saved"""
    try:
        # Check if profile exists
        if created:
            # Only create profile if it doesn't exist and user was just created
            UserProfile.objects.get_or_create(user=instance)
        else:
            # If user exists but profile doesn't, create it
            UserProfile.objects.get_or_create(user=instance)
    except Exception as e:
        print(f"Error creating user profile: {str(e)}")

class BillingItem(models.Model):
    ITEM_TYPES = [
        ('consultation', 'Consultation'),
        ('procedure', 'Medical Procedure'),
        ('medicine', 'Medicine'),
        ('lab_test', 'Laboratory Test'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.name} - {self.get_item_type_display()}"

class Bill(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('insurance', 'Insurance'),
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='bills')
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE, related_name='bills')
    appointment = models.OneToOneField('Appointment', on_delete=models.CASCADE, related_name='bill')
    clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE)
    
    bill_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Bill #{self.id} - {self.patient.get_full_name()}"
    
    def calculate_total(self):
        """Calculate total bill amount including tax and discount"""
        self.subtotal = sum(item.total for item in self.items.all())
        self.tax = self.subtotal * Decimal('0.18')  # 18% tax
        self.total = self.subtotal + self.tax - self.discount
        self.save()

class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    billing_item = models.ForeignKey(BillingItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        self.total = self.quantity * self.price
        super().save(*args, **kwargs)
        self.bill.calculate_total()

class Payment(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=Bill.PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update bill status based on payments
        total_paid = sum(payment.amount for payment in self.bill.payments.all())
        if total_paid >= self.bill.total:
            self.bill.status = 'paid'
        elif total_paid > 0:
            self.bill.status = 'partial'
        self.bill.save()