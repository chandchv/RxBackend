# core/models.py (or users/models.py)

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import URLValidator
# Consider using a dedicated encryption library
# from cryptography.fernet import Fernet # Example
# from django_cryptography.fields import EncryptedCharField, EncryptedTextField, EncryptedDateField # Example library

# --- Choices ---

ROLE_CHOICES = [
    ('patient', 'Patient'),
    ('doctor', 'Doctor'),
    ('admin', 'Hospital Admin'),
    ('staff', 'Staff'), # General staff role?
    ('lab_technician', 'Lab Technician'),
    ('pharmacy_staff', 'Pharmacy Staff'),
    ('superuser', 'Superuser'), # For Django superusers
]

GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
    ('undisclosed', 'Prefer not to say'),
]

ACCESS_LEVEL_CHOICES = [
    ('read', 'Read Only'),
    ('write', 'Read/Write'),
    ('full', 'Full Access'), # Consider specific permissions granularity
    ('none', 'No Access'), # Explicit denial
]

DOC_STATUS_CHOICES = [
    ('uploaded', 'Uploaded'),
    ('processing', 'Processing'), # e.g., OCR/NLP in progress
    ('completed', 'Completed'),
    ('error', 'Error'),
]

APPT_STATUS_CHOICES = [
    ('scheduled', 'Scheduled'),
    ('confirmed', 'Confirmed'),
    ('completed', 'Completed'),
    ('canceled', 'Canceled'),
    ('no_show', 'No Show'),
]

AUDIT_ACTION_CHOICES = [
    ('create', 'Create'),
    ('view', 'View'),
    ('update', 'Update'),
    ('delete', 'Delete'),
    ('login', 'Login'),
    ('logout', 'Logout'),
    ('export', 'Export'),
    ('emergency_access', 'Emergency Access'),
    ('consent_grant', 'Consent Grant'),
    ('consent_revoke', 'Consent Revoke'),
]

INTEGRATION_TYPE_CHOICES = [
    ('fhir', 'FHIR'),
    ('hl7', 'HL7'),
    ('direct', 'Direct Protocol'),
    ('api', 'Custom API'),
    ('other', 'Other')
]

DATA_SHARING_LEVEL_CHOICES = [
    ('none', 'No Sharing'),
    ('basic', 'Basic Information'),
    ('summary', 'Clinical Summary'),
    ('full', 'Full Record')
]

# --- Base Model for Timestamps ---

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# --- Tenant Model ---

class Hospital(TimeStampedModel):
    """
    Represents a Hospital or Clinic (Tenant) in the multi-tenant system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    # Add other relevant hospital details (website, NPI, etc.)

    class Meta:
        verbose_name = "Hospital / Organization"
        verbose_name_plural = "Hospitals / Organizations"
        ordering = ['name']

    def __str__(self):
        return self.name

# --- Custom User Model ---

class User(AbstractUser):
    """
    Custom User model extending Django's base user.
    Includes role for RBAC and optional hospital affiliation.
    Password management and standard fields (first_name, last_name, email)
    are handled by AbstractUser.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient', db_index=True)
    # Affiliation for non-patient users (Doctors, Admins, Staff)
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.PROTECT, # Prevent deleting hospital if users are linked
        null=True, blank=True, # Allow null for patients and superusers
        related_name='staff_members',
        help_text="Hospital affiliation for staff roles (Doctor, Admin, etc.)"
    )
    
    # Override groups and user_permissions with custom related_names
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )

    class Meta:
        verbose_name = "User Account"
        verbose_name_plural = "User Accounts"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def is_patient(self):
        return self.role == 'patient'

    @property
    def is_doctor(self):
        return self.role == 'doctor'

    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser

# --- Profile Models (linked One-to-One with User) ---

class Patient(TimeStampedModel):
    """
    Patient profile containing demographic and PHI information.
    Linked one-to-one with a User account for portal access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, # If User account is deleted, Patient profile goes too
        related_name='patient_profile'
    )
    # PHI - Requires encryption at rest
    first_name = models.CharField(max_length=100, help_text="Patient's legal first name.")
    last_name = models.CharField(max_length=100, db_index=True, help_text="Patient's legal last name.")
    date_of_birth = models.DateField(help_text="Patient's date of birth.")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True, help_text="Primary contact phone number.")
    address = models.CharField(max_length=255, blank=True, help_text="Patient's primary address.")
    # Add other PHI: SSN (highly sensitive!), emergency contact, insurance info - ALL require encryption

    primary_hospital = models.ForeignKey(
        Hospital,
        on_delete=models.PROTECT, # Protect the primary hospital link
        related_name='primary_patients',
        help_text="Patient's primary associated hospital/clinic (for tenancy context)."
    )
    # Global identifier (e.g., MRN or unique health ID)
    # PHI - Requires encryption if sensitive (like MRN)
    global_identifier = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text="Unique global identifier for the patient (e.g., system-wide MRN)."
    )

    # Additional fields for patient dashboard
    blood_group = models.CharField(max_length=10, blank=True, help_text="Patient's blood group")
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Weight in kg")
    allergies = models.TextField(blank=True, help_text="Known allergies")
    chronic_conditions = models.TextField(blank=True, help_text="Chronic medical conditions")
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_id = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to='patient_photos/', null=True, blank=True)

    external_provider_ids = models.JSONField(
        default=dict,
        help_text="Map of external provider IDs for this patient"
    )
    data_sharing_preferences = models.JSONField(
        default=dict,
        help_text="Patient's preferences for data sharing"
    )
    last_record_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time records were synced with external providers"
    )

    class Meta:
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['date_of_birth']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ID: {self.global_identifier})"

    # Property to easily access associated hospital for tenancy checks
    @property
    def hospital(self):
        return self.primary_hospital

class Doctor(TimeStampedModel):
    """
    Doctor profile containing professional information.
    Linked one-to-one with a User account.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
        limit_choices_to={'role': 'doctor'} # Ensure linked user has doctor role
    )
    # PHI (potentially, depending on context) - Requires encryption if treated as such
    specialty = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=50, blank=True, db_index=True)
    # Add NPI, qualifications, etc.

    # Primary hospital affiliation (simplest model, as described)
    # hospital = models.ForeignKey(
    #     Hospital,
    #     on_delete=models.PROTECT,
    #     related_name='affiliated_doctors',
    #     help_text="Primary hospital affiliation for this doctor."
    # )
    # If doctors can work at multiple hospitals, use M2M:
    hospitals = models.ManyToManyField(
        Hospital,
        related_name='affiliated_doctors',
        through='DoctorHospitalAffiliation',
        help_text="Hospitals where this doctor practices."
    )

    class Meta:
        verbose_name = "Doctor Profile"
        verbose_name_plural = "Doctor Profiles"
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} ({self.specialty or 'General'})"

    # Property to easily access primary hospital if using M2M (e.g., the first one or based on a flag)
    # Or directly access the hospital field if using ForeignKey
    @property
    def primary_hospital(self):
        # Example logic for M2M - adapt as needed
        affiliation = self.affiliations.filter(is_primary=True).first()
        return affiliation.hospital if affiliation else self.hospitals.first()

class DoctorHospitalAffiliation(TimeStampedModel):
    """Through model for Doctor-Hospital ManyToMany relationship."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="affiliations")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="doctor_affiliations")
    is_primary = models.BooleanField(default=False, help_text="Is this the doctor's primary practice location?")
    # Add specific roles/privileges at this hospital if needed

    class Meta:
        verbose_name = "Doctor Hospital Affiliation"
        verbose_name_plural = "Doctor Hospital Affiliations"
        unique_together = ('doctor', 'hospital')
        ordering = ['doctor__user__last_name', 'hospital__name']

    def __str__(self):
        return f"{self.doctor} @ {self.hospital} {'(Primary)' if self.is_primary else ''}"


# --- Access Control & Consent ---

class PatientConsent(TimeStampedModel):
    """
    Records patient consent granting access to their records.
    Enforces patient control over PHI access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consents_given')
    # Grantee can be a Doctor or potentially other staff/admin user
    grantee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consents_received',
        # Limit choices to relevant roles if desired
        # limit_choices_to=models.Q(role='doctor') | models.Q(role='admin') | models.Q(role='staff')
    )
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='read')
    start_date = models.DateField(null=True, blank=True, help_text="Date consent becomes active.")
    end_date = models.DateField(null=True, blank=True, help_text="Date consent expires (optional).")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep record even if grantor account deleted
        null=True, blank=True,
        related_name='consents_managed',
        help_text="User who granted the consent (usually the patient)."
    )
    # granted_at is inherited from TimeStampedModel (created_at)
    revoked_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when consent was revoked.")
    is_active = models.BooleanField(default=True, help_text="Indicates if the consent is currently active (not revoked and within date range).")

    class Meta:
        verbose_name = "Patient Consent"
        verbose_name_plural = "Patient Consents"
        # Ensure a patient can't grant the same grantee access multiple times concurrently?
        # unique_together = ('patient', 'grantee', 'access_level') # Might be too strict if dates differ
        indexes = [
            models.Index(fields=['patient', 'grantee']),
            models.Index(fields=['patient', 'is_active', 'end_date']),
        ]
        ordering = ['patient', '-created_at']

    def __str__(self):
        status = "Revoked" if self.revoked_at else ("Active" if self.is_active else "Inactive")
        return f"Consent for {self.patient} granted to {self.grantee} ({self.access_level}) - Status: {status}"

    # Add logic in save() or manager to update is_active based on dates/revoked_at

# --- Emergency Access ---

class EmergencyAccessLog(TimeStampedModel):
    """
    Logs 'break-glass' access requests and grants.
    Crucial for HIPAA audit trails when bypassing standard consent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # User requesting access (should typically be a doctor)
    requesting_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, # Keep log even if user deleted
        related_name='emergency_access_requests'
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='emergency_access_logs')
    # requested_at is inherited from TimeStampedModel (created_at)
    justification = models.TextField(help_text="Reason provided for requiring emergency access.")
    access_granted = models.BooleanField(default=False, help_text="Was emergency access ultimately granted?")
    # User who approved the request (could be automated/system or an admin)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emergency_access_approvals'
    )
    granted_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when access was granted.")
    # Link to the specific hospital context
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL, # Keep log if hospital deleted
        null=True, blank=True,
        related_name='emergency_access_logs'
    )

    class Meta:
        verbose_name = "Emergency Access Log"
        verbose_name_plural = "Emergency Access Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'created_at']),
            models.Index(fields=['requesting_user', 'created_at']),
            models.Index(fields=['hospital', 'created_at']),
        ]

    def __str__(self):
        granted_status = "Granted" if self.access_granted else "Denied/Pending"
        return f"Emergency Access Request for {self.patient} by {self.requesting_user} at {self.created_at:%Y-%m-%d %H:%M} - {granted_status}"


# --- Patient Records (Documents) ---

def patient_document_path(instance, filename):
    """Generates upload path: MEDIA_ROOT/hospital_<id>/patient_<id>/<uuid>_<filename>"""
    # Ensure patient and hospital are set
    if not instance.patient_id or not instance.hospital_id:
         # Handle error or default path - Should not happen if saved correctly
         return f'uploads/unknown/{uuid.uuid4()}_{filename}'
    return f'hospital_{instance.hospital_id}/patient_{instance.patient_id}/{uuid.uuid4()}_{filename}'


class Document(TimeStampedModel):
    """
    Metadata for uploaded patient documents (PDF, images, DICOM, etc.).
    Actual file stored securely (e.g., S3 with encryption), path stored here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep record if uploader deleted
        null=True, blank=True,
        related_name='uploaded_documents'
    )
    # Tenant identifier
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='documents')

    # File itself - stored securely, path/reference managed by Django
    # File content requires encryption at rest in storage system (S3, etc.)
    file = models.FileField(
        upload_to=patient_document_path,
        help_text="Reference to the securely stored document file."
    )
    # Metadata
    file_name = models.CharField(max_length=255, blank=True, help_text="Original filename at time of upload.")
    content_type = models.CharField(max_length=100, blank=True, help_text="MIME type of the file.")
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="Size of the file in bytes.")
    # upload_timestamp is inherited from TimeStampedModel (created_at)
    status = models.CharField(max_length=20, choices=DOC_STATUS_CHOICES, default='uploaded', db_index=True)
    description = models.CharField(max_length=255, blank=True, help_text="Optional description of the document.")

    class Meta:
        verbose_name = "Patient Document"
        verbose_name_plural = "Patient Documents"
        ordering = ['patient', '-created_at']
        indexes = [
            models.Index(fields=['patient', 'created_at']),
            models.Index(fields=['hospital', 'created_at']),
        ]

    def __str__(self):
        return f"Document for {self.patient} ({self.file_name or 'No Name'}) - Status: {self.status}"

    def save(self, *args, **kwargs):
        # Automatically set filename and hospital if not set explicitly
        if not self.file_name and self.file:
            self.file_name = self.file.name.split('/')[-1] # Get base name
        if not self.hospital_id and self.patient_id:
             self.hospital = self.patient.primary_hospital # Inherit from patient
        super().save(*args, **kwargs)

class OCRText(TimeStampedModel):
    """
    Stores the extracted text content from a Document via OCR.
    Enables full-text search across document contents.
    """
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE, # Delete OCR text if document is deleted
        primary_key=True,
        related_name='ocr_text'
    )
    # PHI - Requires encryption if storing sensitive text content directly
    full_text = models.TextField(blank=True, help_text="Full text extracted from the document via OCR.")
    # extracted_at is inherited from TimeStampedModel (created_at)

    # For PostgreSQL Full-Text Search:
    # from django.contrib.postgres.search import SearchVectorField
    # from django.contrib.postgres.indexes import GinIndex
    # search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = "OCR Extracted Text"
        verbose_name_plural = "OCR Extracted Texts"
        # indexes = [
        #     GinIndex(fields=['search_vector']) # If using PostgreSQL FTS
        # ]

    def __str__(self):
        return f"OCR Text for {self.document}"

    # Add logic (e.g., signal on Document save/update) to trigger OCR and populate this.
    # Add logic to update search_vector if using FTS.


# --- Structured Clinical Data Models ---
# These models represent structured data, potentially extracted from documents or entered manually.

class Prescription(TimeStampedModel):
    """Represents a medication prescription order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    prescribing_doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_prescriptions'
    )
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='prescriptions')

    # Enhanced prescription fields
    medication_name = models.CharField(max_length=255, help_text="Name of the prescribed medication")
    strength = models.CharField(max_length=50, help_text="Strength of the medication (e.g., 500mg)")
    dosage_form = models.CharField(
        max_length=50,
        choices=[
            ('tablet', 'Tablet'),
            ('capsule', 'Capsule'),
            ('syrup', 'Syrup'),
            ('injection', 'Injection'),
            ('cream', 'Cream'),
            ('drops', 'Drops'),
            ('inhaler', 'Inhaler'),
            ('other', 'Other')
        ]
    )
    frequency = models.CharField(max_length=100, help_text="How often to take (e.g., twice daily)")
    duration = models.CharField(max_length=100, help_text="Duration of the prescription")
    quantity = models.IntegerField(help_text="Total quantity prescribed")
    route = models.CharField(
        max_length=50,
        choices=[
            ('oral', 'Oral'),
            ('topical', 'Topical'),
            ('injection', 'Injection'),
            ('inhale', 'Inhale'),
            ('other', 'Other')
        ],
        default='oral'
    )
    instructions = models.TextField(help_text="Detailed instructions for taking the medication")
    side_effects = models.TextField(blank=True, help_text="Potential side effects")
    warnings = models.TextField(blank=True, help_text="Important warnings or contraindications")
    refills = models.IntegerField(default=0, help_text="Number of refills allowed")
    refills_remaining = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    expiry_date = models.DateField(null=True, blank=True)
    pharmacy_notes = models.TextField(blank=True)
    is_controlled_substance = models.BooleanField(default=False)
    
    # Timestamps for prescription lifecycle
    filled_date = models.DateTimeField(null=True, blank=True)
    last_filled_date = models.DateTimeField(null=True, blank=True)
    cancelled_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prescription"
        verbose_name_plural = "Prescriptions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'created_at']),
            models.Index(fields=['hospital', 'created_at']),
            models.Index(fields=['prescribing_doctor', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Prescription: {self.medication_name} {self.strength} for {self.patient}"

    def save(self, *args, **kwargs):
        if not self.hospital_id:
            if self.patient_id:
                self.hospital = self.patient.primary_hospital
            elif self.prescribing_doctor_id and self.prescribing_doctor.primary_hospital:
                self.hospital = self.prescribing_doctor.primary_hospital
        super().save(*args, **kwargs)


class LabResult(TimeStampedModel):
    """Represents a single laboratory test result."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_results')
    # Tenant identifier
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='lab_results')

    # PHI - Requires encryption
    test_name = models.CharField(max_length=255, db_index=True, help_text="Name of the lab test performed.")
    result_value = models.CharField(max_length=255, help_text="The quantitative or qualitative result.")
    units = models.CharField(max_length=50, blank=True, help_text="Units of measurement for the result.")
    reference_range = models.CharField(max_length=100, blank=True, help_text="Normal reference range for the test.")
    result_date = models.DateTimeField(help_text="Date and time the result was recorded/reported.")
    lab_notes = models.TextField(blank=True, help_text="Notes from the lab or interpreting physician.")

    # Optional: Link to ordering doctor
    ordering_doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordered_lab_results'
    )
    # Optional: Link to source document
    source_document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lab_results_extracted'
    )

    class Meta:
        verbose_name = "Lab Result"
        verbose_name_plural = "Lab Results"
        ordering = ['patient', '-result_date']
        indexes = [
            models.Index(fields=['patient', 'result_date']),
            models.Index(fields=['hospital', 'result_date']),
            models.Index(fields=['patient', 'test_name']),
        ]

    def __str__(self):
        return f"Lab Result for {self.patient}: {self.test_name} = {self.result_value} {self.units}"

    def save(self, *args, **kwargs):
        # Ensure hospital is set
        if not self.hospital_id and self.patient_id:
            self.hospital = self.patient.primary_hospital
        super().save(*args, **kwargs)


class Diagnosis(TimeStampedModel):
    """Represents a clinical diagnosis made for a patient."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diagnoses')
    # Doctor making the diagnosis
    diagnosing_doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='made_diagnoses'
    )
    # Tenant identifier
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='diagnoses')

    # PHI - Requires encryption
    diagnosis_code = models.CharField(max_length=50, db_index=True, blank=True, help_text="Standardized diagnosis code (e.g., ICD-10).")
    description = models.TextField(help_text="Description of the diagnosis.")
    diagnosis_date = models.DateTimeField(help_text="Date and time the diagnosis was made or recorded.")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Is this considered an active/ongoing diagnosis?")

    # Optional: Link to source document
    source_document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='diagnoses_extracted'
    )

    class Meta:
        verbose_name = "Diagnosis"
        verbose_name_plural = "Diagnoses"
        ordering = ['patient', '-diagnosis_date']
        indexes = [
            models.Index(fields=['patient', 'diagnosis_date']),
            models.Index(fields=['hospital', 'diagnosis_date']),
            models.Index(fields=['patient', 'is_active', 'diagnosis_code']),
        ]

    def __str__(self):
        code = f" ({self.diagnosis_code})" if self.diagnosis_code else ""
        return f"Diagnosis for {self.patient}: {self.description[:50]}...{code}"

    def save(self, *args, **kwargs):
        # Ensure hospital is set
        if not self.hospital_id:
             if self.patient_id:
                 self.hospital = self.patient.primary_hospital
             elif self.diagnosing_doctor_id and self.diagnosing_doctor.primary_hospital:
                  self.hospital = self.diagnosing_doctor.primary_hospital
        super().save(*args, **kwargs)


class Appointment(TimeStampedModel):
    """Represents a scheduled appointment."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appointments'
    )
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='appointments')

    # Enhanced appointment fields
    appointment_date = models.DateField(help_text="Date of the appointment")
    appointment_time = models.TimeField(help_text="Time of the appointment")
    duration = models.IntegerField(default=30, help_text="Duration in minutes")
    appointment_type = models.CharField(
        max_length=50,
        choices=[
            ('regular', 'Regular Checkup'),
            ('followup', 'Follow-up'),
            ('specialist', 'Specialist Consultation'),
            ('emergency', 'Emergency'),
        ],
        default='regular'
    )
    reason = models.TextField(blank=True, help_text="Reason for the appointment")
    symptoms = models.TextField(blank=True, help_text="Patient's symptoms")
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('confirmed', 'Confirmed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('no_show', 'No Show'),
            ('rescheduled', 'Rescheduled')
        ],
        default='scheduled'
    )
    cancellation_reason = models.TextField(blank=True, help_text="Reason for cancellation if applicable")
    reminder_sent = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_appointments'
    )
    notes = models.TextField(blank=True, help_text="Additional notes about the appointment")
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ['-appointment_date', '-appointment_time']
        indexes = [
            models.Index(fields=['patient', 'appointment_date']),
            models.Index(fields=['doctor', 'appointment_date']),
            models.Index(fields=['hospital', 'appointment_date']),
            models.Index(fields=['status', 'appointment_date']),
        ]

    def __str__(self):
        doc_name = f"with Dr. {self.doctor.user.get_full_name()}" if self.doctor else ""
        return f"Appointment for {self.patient} {doc_name} on {self.appointment_date} at {self.appointment_time} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.hospital_id:
            if self.doctor_id and self.doctor.primary_hospital:
                self.hospital = self.doctor.primary_hospital
            elif self.patient_id:
                self.hospital = self.patient.primary_hospital
        super().save(*args, **kwargs)


# --- Optional: Mapping Local Patient IDs ---

class PatientIdentifier(TimeStampedModel):
    """
    Maps a hospital's local patient identifier (e.g., MRN) to the global Patient profile.
    Useful for interoperability and resolving IDs across tenants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='hospital_identifiers')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='patient_identifiers')
    # PHI - Requires encryption (as it's often an MRN)
    hospital_patient_id = models.CharField(
        max_length=100, db_index=True,
        help_text="The patient identifier specific to this hospital (e.g., MRN)."
    )

    class Meta:
        verbose_name = "Patient Hospital Identifier"
        verbose_name_plural = "Patient Hospital Identifiers"
        # Ensure the hospital-specific ID is unique within that hospital
        unique_together = ('hospital', 'hospital_patient_id')
        # Optional: Ensure a patient has only one ID per hospital
        # unique_together = ('patient', 'hospital')
        ordering = ['patient', 'hospital']

    def __str__(self):
        return f"{self.patient} at {self.hospital}: ID {self.hospital_patient_id}"


# --- Audit Logging ---

class AuditLog(models.Model):
    """
    Detailed audit trail for HIPAA compliance. Logs access and modifications to PHI.
    Should be written to via signals or middleware, and ideally be immutable.
    """
    id = models.BigAutoField(primary_key=True) # Use BigAutoField for potentially high volume
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    # User performing the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep log even if user deleted
        null=True, blank=True,
        related_name='audit_log_entries'
    )
    action = models.CharField(max_length=20, choices=AUDIT_ACTION_CHOICES, db_index=True)
    # Target object details
    target_model = models.CharField(max_length=100, blank=True, null=True, help_text="Model name being affected (e.g., 'Patient').")
    target_pk = models.CharField(max_length=36, blank=True, null=True, help_text="Primary key of the affected record (UUID or other ID).")
    # Store details of changes (e.g., field diffs) - Potentially contains PHI
    changes = models.JSONField(null=True, blank=True, help_text="JSON representation of changes made (optional).")
    description = models.TextField(blank=True, help_text="Contextual description of the action.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # Tenant context
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL, # Keep log if hospital deleted
        null=True, blank=True,
        related_name='audit_log_entries'
    )

    class Meta:
        verbose_name = "Audit Log Entry"
        verbose_name_plural = "Audit Log Entries"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['target_model', 'target_pk']),
            models.Index(fields=['hospital', 'timestamp']),
        ]

    def __str__(self):
        user_info = f"User {self.user_id}" if self.user_id else "System"
        target_info = f" on {self.target_model} ({self.target_pk})" if self.target_model else ""
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} - {user_info} performed {self.action}{target_info}"

class ExternalHealthcareProvider(TimeStampedModel):
    """
    Represents external healthcare providers/institutions that can integrate with our system
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    provider_type = models.CharField(
        max_length=50,
        choices=[
            ('hospital', 'Hospital'),
            ('clinic', 'Clinic'),
            ('lab', 'Laboratory'),
            ('pharmacy', 'Pharmacy'),
            ('other', 'Other')
        ]
    )
    identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text="National Provider Identifier or other unique ID"
    )
    api_endpoint = models.URLField(validators=[URLValidator()])
    api_key = models.CharField(max_length=255, blank=True)
    integration_type = models.CharField(
        max_length=20,
        choices=INTEGRATION_TYPE_CHOICES,
        default='fhir'
    )
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    supported_data_types = models.JSONField(
        default=list,
        help_text="Types of data this provider can exchange"
    )

    class Meta:
        verbose_name = "External Healthcare Provider"
        verbose_name_plural = "External Healthcare Providers"

    def __str__(self):
        return f"{self.name} ({self.provider_type})"

class HealthDataExchange(TimeStampedModel):
    """
    Tracks health data exchange between our system and external providers
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='data_exchanges')
    external_provider = models.ForeignKey(
        ExternalHealthcareProvider,
        on_delete=models.CASCADE,
        related_name='data_exchanges'
    )
    direction = models.CharField(
        max_length=20,
        choices=[
            ('inbound', 'Inbound'),
            ('outbound', 'Outbound'),
            ('bidirectional', 'Bidirectional')
        ]
    )
    data_type = models.CharField(
        max_length=50,
        choices=[
            ('demographics', 'Demographics'),
            ('medications', 'Medications'),
            ('conditions', 'Conditions'),
            ('allergies', 'Allergies'),
            ('lab_results', 'Lab Results'),
            ('imaging', 'Imaging'),
            ('procedures', 'Procedures'),
            ('immunizations', 'Immunizations'),
            ('full_record', 'Full Health Record')
        ]
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('partial', 'Partially Completed')
        ],
        default='pending'
    )
    exchange_date = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)
    exchange_reference = models.CharField(max_length=255, blank=True, help_text="External reference number")

    class Meta:
        verbose_name = "Health Data Exchange"
        verbose_name_plural = "Health Data Exchanges"
        ordering = ['-exchange_date']

    def __str__(self):
        return f"{self.direction} exchange with {self.external_provider} for {self.patient}"

class PatientDataConsent(TimeStampedModel):
    """
    Manages patient consent for data sharing with external providers
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='data_sharing_consents')
    external_provider = models.ForeignKey(
        ExternalHealthcareProvider,
        on_delete=models.CASCADE,
        related_name='patient_consents'
    )
    sharing_level = models.CharField(
        max_length=20,
        choices=DATA_SHARING_LEVEL_CHOICES,
        default='none'
    )
    consent_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    specific_consents = models.JSONField(
        default=list,
        help_text="Specific data types consented for sharing"
    )
    revocation_date = models.DateTimeField(null=True, blank=True)
    consent_document = models.FileField(upload_to='consent_documents/', null=True, blank=True)

    class Meta:
        verbose_name = "Patient Data Consent"
        verbose_name_plural = "Patient Data Consents"
        unique_together = ['patient', 'external_provider']
        ordering = ['-consent_date']

    def __str__(self):
        return f"Consent for {self.patient} with {self.external_provider}"

class StandardizedHealthRecord(TimeStampedModel):
    """
    Stores standardized health record data (FHIR/HL7) for interoperability
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='standardized_records')
    record_type = models.CharField(
        max_length=50,
        choices=[
            ('fhir_patient', 'FHIR Patient Resource'),
            ('fhir_condition', 'FHIR Condition Resource'),
            ('fhir_medication', 'FHIR Medication Resource'),
            ('fhir_observation', 'FHIR Observation Resource'),
            ('hl7_adt', 'HL7 ADT Message'),
            ('hl7_oru', 'HL7 ORU Message'),
            ('ccda', 'C-CDA Document'),
            ('other', 'Other Format')
        ]
    )
    data = models.JSONField(help_text="Standardized health record data")
    source_system = models.ForeignKey(
        ExternalHealthcareProvider,
        on_delete=models.SET_NULL,
        null=True,
        related_name='provided_records'
    )
    version = models.CharField(max_length=50, help_text="Version of the standard used")
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of validation errors"
    )
    last_updated = models.DateTimeField(auto_now=True)
    external_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="External reference ID from source system"
    )

    class Meta:
        verbose_name = "Standardized Health Record"
        verbose_name_plural = "Standardized Health Records"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'record_type']),
            models.Index(fields=['source_system', 'external_reference']),
        ]

    def __str__(self):
        return f"{self.record_type} for {self.patient} from {self.source_system}"

class DataMappingConfiguration(TimeStampedModel):
    """
    Configures how data is mapped between our system and external systems
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_provider = models.ForeignKey(
        ExternalHealthcareProvider,
        on_delete=models.CASCADE,
        related_name='data_mappings'
    )
    local_model = models.CharField(max_length=100, help_text="Name of local model")
    external_model = models.CharField(max_length=100, help_text="Name of external model/resource")
    mapping_rules = models.JSONField(help_text="Rules for mapping fields between systems")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Data Mapping Configuration"
        verbose_name_plural = "Data Mapping Configurations"
        unique_together = ['external_provider', 'local_model', 'external_model']

    def __str__(self):
        return f"Mapping: {self.local_model} to {self.external_model} for {self.external_provider}"