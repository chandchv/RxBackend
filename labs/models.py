from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import Patient, Doctor
from django.utils import timezone

# Create your models here.

class LabProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lab_profile'
    )
    name = models.CharField(max_length=255, unique=True)
    lab_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    registration_number = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        null=True,
        help_text="Lab's official registration/license number"
    )
    contact_person = models.CharField(max_length=255, help_text="Name of the primary contact person")
    contact_person_designation = models.CharField(max_length=100, help_text="Designation of the contact person")
    address = models.TextField()
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True)
    accreditation_details = models.TextField(blank=True)
    certifications = models.JSONField(
        default=list,
        help_text="List of standard lab certifications (e.g., ISO, NABL, CAP)",
        blank=True
    )
    logo = models.ImageField(upload_to='lab_logos/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Lab Profile'
        verbose_name_plural = 'Lab Profiles'
        ordering = ['name']

class TestDefinition(models.Model):
    name = models.CharField(max_length=255, unique=True)
    short_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="e.g., LOINC code"
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    preparation_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Test Definition'
        verbose_name_plural = 'Test Definitions'
        ordering = ['name']

class LabTestOffering(models.Model):
    lab = models.ForeignKey('users.Lab', on_delete=models.CASCADE, related_name='test_offerings')
    test = models.ForeignKey('TestDefinition', on_delete=models.CASCADE, related_name='offered_by_labs')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    turnaround_time_hours = models.IntegerField()
    offers_home_collection = models.BooleanField(default=False)
    specific_instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['lab', 'test']
        ordering = ['test__name']

    def __str__(self):
        return f"{self.lab.name} - {self.test.name}"

class ExternalLabTestOffering(models.Model):
    lab_profile = models.ForeignKey('LabProfile', on_delete=models.CASCADE, related_name='test_offerings')
    test = models.ForeignKey('TestDefinition', on_delete=models.CASCADE, related_name='offered_by_external_labs')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    turnaround_time_hours = models.IntegerField()
    offers_home_collection = models.BooleanField(default=False)
    specific_instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['lab_profile', 'test']
        ordering = ['test__name']

    def __str__(self):
        return f"{self.lab_profile.name} - {self.test.name}"

class LabOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING_PATIENT_CHOICE', 'Pending Patient Choice'),
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('PENDING_LAB', 'Pending Lab Confirmation/Visit'),
        ('PROCESSING', 'Processing at Lab'),
        ('RESULT_UPLOADED', 'Result Uploaded'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
        ('FAILED', 'Payment Failed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='lab_orders')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_orders')
    tests = models.ManyToManyField(TestDefinition, through='LabOrderTest')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_PATIENT_CHOICE')
    doctor_recommendation = models.ForeignKey(LabProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='recommended_orders')
    chosen_lab = models.ForeignKey(LabProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='chosen_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.patient.user.get_full_name()}"

class LabOrderTest(models.Model):
    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='order_tests')
    test = models.ForeignKey(TestDefinition, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('order', 'test')

    def __str__(self):
        return f"{self.order} - {self.test.name}"

class LabResult(models.Model):
    order = models.OneToOneField(LabOrder, on_delete=models.CASCADE, related_name='result')
    result_file = models.FileField(upload_to='lab_results/%Y/%m/', null=True, blank=True)
    structured_result = models.JSONField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by_lab = models.ForeignKey(LabProfile, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    file_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash of the uploaded file for integrity check")
    lab_metadata = models.JSONField(null=True, blank=True, help_text="e.g., Lab Name, Technician, Test Method provided at upload")

    def __str__(self):
        return f"Result for Order #{self.order.id}"

class CommissionRule(models.Model):
    """
    Defines commission rules for labs and doctors.
    A null lab field indicates the global default rule.
    """
    lab = models.OneToOneField(
        LabProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Leave blank for global default rule"
    )
    doctor_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="e.g., 10.00 for 10%"
    )
    platform_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="e.g., 5.00 for 5%"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Commission Rule"
        verbose_name_plural = "Commission Rules"

    def __str__(self):
        if self.lab:
            return f"Commission Rule for {self.lab.name}"
        return "Global Default Commission Rule"

    def clean(self):
        """
        Ensure the sum of percentages doesn't exceed 100%
        """
        if self.doctor_percentage + self.platform_percentage > 100:
            raise ValidationError("The sum of doctor and platform percentages cannot exceed 100%")

class CommissionLedger(models.Model):
    """
    Tracks commission transactions for doctors and platform fees.
    """
    TRANSACTION_TYPES = [
        ('doctor_commission', 'Doctor Commission'),
        ('platform_fee', 'Platform Fee'),
    ]

    STATUS_CHOICES = [
        ('EARNED', 'Earned'),
        ('PENDING_PAYOUT', 'Pending Payout'),
        ('PAID', 'Paid'),
    ]

    order = models.ForeignKey(
        LabOrder,
        on_delete=models.PROTECT,
        related_name='commission_transactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='commission_ledger'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    rule_used = models.ForeignKey(
        CommissionRule,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ledger_entries'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        default='doctor_commission'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='EARNED'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commission Ledger Entry"
        verbose_name_plural = "Commission Ledger Entries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} for Order #{self.order.id}"

    def save(self, *args, **kwargs):
        """
        Update paid_at when status changes to PAID
        """
        if self.status == 'PAID' and not self.paid_at:
            self.paid_at = timezone.now()
        super().save(*args, **kwargs)
