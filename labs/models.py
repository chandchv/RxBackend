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
        return f"{self.transaction_type} - {self.amount} for {self.user}"

    def save(self, *args, **kwargs):
        if self.status == 'PAID' and not self.paid_at:
            self.paid_at = timezone.now()
        super().save(*args, **kwargs)

# ===== SPECIMEN MANAGEMENT MODELS =====

class SpecimenContainer(models.Model):
    """Barcode-labeled specimen containers for easy identification"""
    CONTAINER_TYPES = [
        ('VACUTAINER_RED', 'BD Vacutainer Red Top'),
        ('VACUTAINER_PURPLE', 'BD Vacutainer Purple Top'),
        ('VACUTAINER_BLUE', 'BD Vacutainer Blue Top'),
        ('VACUTAINER_GREEN', 'BD Vacutainer Green Top'),
        ('URINE_CONTAINER', 'Urine Collection Container'),
        ('STOOL_CONTAINER', 'Stool Collection Container'),
        ('SWAB_CONTAINER', 'Swab Container'),
        ('CUSTOM', 'Custom Container'),
    ]
    
    barcode = models.CharField(max_length=50, unique=True, help_text="Unique barcode for specimen identification")
    container_type = models.CharField(max_length=20, choices=CONTAINER_TYPES)
    lab_profile = models.ForeignKey(LabProfile, on_delete=models.CASCADE, related_name='specimen_containers')
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Container {self.barcode} ({self.get_container_type_display()})"

class Specimen(models.Model):
    """Complete specimen management with barcode tracking"""
    SPECIMEN_TYPES = [
        ('BLOOD', 'Blood'),
        ('URINE', 'Urine'),
        ('STOOL', 'Stool'),
        ('SWAB', 'Swab'),
        ('TISSUE', 'Tissue'),
        ('CSF', 'Cerebrospinal Fluid'),
        ('SALIVA', 'Saliva'),
        ('OTHER', 'Other'),
    ]
    
    COLLECTION_METHODS = [
        ('VENIPUNCTURE', 'Venipuncture'),
        ('FINGER_STICK', 'Finger Stick'),
        ('HEEL_STICK', 'Heel Stick'),
        ('MIDSTREAM', 'Midstream Urine'),
        ('RANDOM', 'Random Urine'),
        ('SWAB', 'Swab Collection'),
        ('BIOPSY', 'Biopsy'),
        ('OTHER', 'Other'),
    ]
    
    specimen_id = models.CharField(max_length=50, unique=True, help_text="Unique specimen identifier")
    container = models.ForeignKey(SpecimenContainer, on_delete=models.PROTECT, related_name='specimens')
    lab_order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='specimens')
    specimen_type = models.CharField(max_length=20, choices=SPECIMEN_TYPES)
    collection_method = models.CharField(max_length=20, choices=COLLECTION_METHODS)
    collection_date = models.DateTimeField()
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='collected_specimens')
    collection_notes = models.TextField(blank=True)
    volume_ml = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    color = models.CharField(max_length=50, blank=True)
    appearance = models.CharField(max_length=100, blank=True)
    batch_number = models.CharField(max_length=50, blank=True, help_text="Batch for processing")
    processing_priority = models.CharField(max_length=20, choices=[
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('STAT', 'Stat'),
        ('EMERGENCY', 'Emergency'),
    ], default='ROUTINE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Specimen {self.specimen_id} - {self.specimen_type}"

class SpecimenProcessing(models.Model):
    """Track specimen processing workflow"""
    specimen = models.OneToOneField(Specimen, on_delete=models.CASCADE, related_name='processing')
    received_at_lab = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='received_specimens')
    processing_started = models.DateTimeField(null=True, blank=True)
    processing_completed = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='processed_specimens')
    processing_notes = models.TextField(blank=True)
    quality_check_passed = models.BooleanField(null=True, blank=True)
    quality_check_notes = models.TextField(blank=True)
    storage_location = models.CharField(max_length=100, blank=True)
    disposal_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Processing for {self.specimen.specimen_id}"

# ===== QUALITY CONTROL MODELS =====

class QualityControlTest(models.Model):
    """Quality control test definitions"""
    QC_TYPES = [
        ('INTERNAL', 'Internal QC'),
        ('EXTERNAL', 'External QC'),
        ('PROFICIENCY', 'Proficiency Testing'),
    ]
    
    name = models.CharField(max_length=255)
    test_definition = models.ForeignKey(TestDefinition, on_delete=models.CASCADE, related_name='qc_tests')
    qc_type = models.CharField(max_length=20, choices=QC_TYPES)
    frequency = models.CharField(max_length=50, help_text="e.g., Daily, Weekly, Monthly")
    target_value = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    acceptable_range_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    acceptable_range_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    westgard_rules = models.JSONField(default=list, blank=True, help_text="List of Westgard rules to apply")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.test_definition.name}"

class QCResult(models.Model):
    """Quality control test results with Levey-Jennings chart data"""
    qc_test = models.ForeignKey(QualityControlTest, on_delete=models.CASCADE, related_name='results')
    specimen = models.ForeignKey(Specimen, on_delete=models.CASCADE, related_name='qc_results')
    result_value = models.DecimalField(max_digits=10, decimal_places=4)
    run_date = models.DateTimeField()
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    instrument = models.CharField(max_length=100, blank=True)
    lot_number = models.CharField(max_length=50, blank=True)
    is_in_control = models.BooleanField()
    westgard_violations = models.JSONField(default=list, blank=True)
    corrective_action = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reviewed_qc_results')
    review_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"QC Result {self.id} - {self.qc_test.name}"

# ===== RESULT REPORTING MODELS =====

class LabReport(models.Model):
    """Comprehensive lab report with approval workflow"""
    REPORT_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('REVIEWED', 'Reviewed'),
        ('APPROVED', 'Approved'),
        ('RELEASED', 'Released to Patient'),
        ('AMENDED', 'Amended'),
    ]
    
    lab_order = models.OneToOneField(LabOrder, on_delete=models.CASCADE, related_name='report')
    report_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=REPORT_STATUS, default='DRAFT')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_reports')
    approved_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    clinical_interpretation = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    critical_values = models.JSONField(default=list, blank=True)
    turnaround_time_hours = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"Report {self.report_number} - {self.lab_order}"

class TestResult(models.Model):
    """Individual test results within a report"""
    report = models.ForeignKey(LabReport, on_delete=models.CASCADE, related_name='test_results')
    test_definition = models.ForeignKey(TestDefinition, on_delete=models.CASCADE)
    specimen = models.ForeignKey(Specimen, on_delete=models.CASCADE, related_name='test_results')
    result_value = models.CharField(max_length=255)
    unit = models.CharField(max_length=20, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    is_abnormal = models.BooleanField(default=False)
    abnormality_type = models.CharField(max_length=20, choices=[
        ('HIGH', 'High'),
        ('LOW', 'Low'),
        ('CRITICAL_HIGH', 'Critical High'),
        ('CRITICAL_LOW', 'Critical Low'),
        ('NORMAL', 'Normal'),
    ], default='NORMAL')
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField()
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='verified_results')
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.test_definition.name} - {self.result_value}"

# ===== COMMUNICATION & DELIVERY MODELS =====

class ReportDelivery(models.Model):
    """Track report delivery to various stakeholders"""
    DELIVERY_METHODS = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('WHATSAPP', 'WhatsApp'),
        ('FAX', 'Fax'),
        ('PORTAL', 'Patient Portal'),
        ('IN_PERSON', 'In Person'),
    ]
    
    DELIVERY_STATUS = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('READ', 'Read'),
    ]
    
    report = models.ForeignKey(LabReport, on_delete=models.CASCADE, related_name='deliveries')
    recipient_type = models.CharField(max_length=20, choices=[
        ('PATIENT', 'Patient'),
        ('DOCTOR', 'Doctor'),
        ('REFERRING_LAB', 'Referring Lab'),
        ('INSURANCE', 'Insurance'),
    ])
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Delivery {self.id} - {self.report.report_number} to {self.recipient_type}"

class CommunicationLog(models.Model):
    """Log all communications with stakeholders"""
    COMMUNICATION_TYPES = [
        ('ORDER_CONFIRMATION', 'Order Confirmation'),
        ('PAYMENT_REMINDER', 'Payment Reminder'),
        ('COLLECTION_REMINDER', 'Collection Reminder'),
        ('RESULT_READY', 'Result Ready'),
        ('CRITICAL_VALUE', 'Critical Value Alert'),
        ('REPORT_DELIVERY', 'Report Delivery'),
        ('GENERAL', 'General Communication'),
    ]
    
    lab_profile = models.ForeignKey(LabProfile, on_delete=models.CASCADE, related_name='communications')
    communication_type = models.CharField(max_length=30, choices=COMMUNICATION_TYPES)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_communications')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    delivery_method = models.CharField(max_length=20, choices=ReportDelivery.DELIVERY_METHODS)
    status = models.CharField(max_length=20, choices=ReportDelivery.DELIVERY_STATUS, default='PENDING')
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    related_order = models.ForeignKey(LabOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.communication_type} - {self.recipient}"

# ===== B2B AUTOMATION MODELS =====

class B2BPartner(models.Model):
    """B2B partners including reference labs, hospitals, clinics"""
    PARTNER_TYPES = [
        ('REFERENCE_LAB', 'Reference Lab'),
        ('HOSPITAL', 'Hospital'),
        ('CLINIC', 'Clinic'),
        ('INSURANCE', 'Insurance Company'),
        ('CORPORATE', 'Corporate Client'),
        ('PHARMACY', 'Pharmacy'),
    ]
    
    name = models.CharField(max_length=255)
    partner_type = models.CharField(max_length=20, choices=PARTNER_TYPES)
    contact_person = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    tax_id = models.CharField(max_length=50, blank=True)
    credit_days = models.IntegerField(default=30, help_text="Payment terms in days")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_partner_type_display()})"

class B2BInvoice(models.Model):
    """Automated B2B invoicing"""
    INVOICE_STATUS = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    partner = models.ForeignKey(B2BPartner, on_delete=models.CASCADE, related_name='invoices')
    lab_profile = models.ForeignKey(LabProfile, on_delete=models.CASCADE, related_name='b2b_invoices')
    invoice_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='DRAFT')
    paid_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.partner.name}"

class B2BInvoiceItem(models.Model):
    """Individual items in B2B invoices"""
    invoice = models.ForeignKey(B2BInvoice, on_delete=models.CASCADE, related_name='items')
    lab_order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='b2b_invoice_items')
    test_name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.test_name} - {self.invoice.invoice_number}"

# ===== ANALYTICS & DASHBOARD MODELS =====

class LabAnalytics(models.Model):
    """Store analytics data for dashboard"""
    lab_profile = models.ForeignKey(LabProfile, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField()
    total_orders = models.IntegerField(default=0)
    completed_orders = models.IntegerField(default=0)
    pending_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    average_turnaround_time = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    quality_control_passed = models.IntegerField(default=0)
    quality_control_failed = models.IntegerField(default=0)
    critical_values_count = models.IntegerField(default=0)
    home_collections = models.IntegerField(default=0)
    lab_visits = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['lab_profile', 'date']
    
    def __str__(self):
        return f"Analytics {self.lab_profile.name} - {self.date}"

class LabUser(models.Model):
    """Model to handle multiple users per lab profile"""
    USER_TYPES = [
        ('LAB_STAFF', 'Lab Staff'),
        ('LAB_TECHNICIAN', 'Lab Technician'),
        ('LAB_MANAGER', 'Lab Manager'),
        ('LAB_ADMIN', 'Lab Administrator'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_user_profile')
    lab_profile = models.ForeignKey(LabProfile, on_delete=models.CASCADE, related_name='lab_users')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='LAB_STAFF')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Lab User'
        verbose_name_plural = 'Lab Users'
        unique_together = ['user', 'lab_profile']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_user_type_display()} at {self.lab_profile.name}"
