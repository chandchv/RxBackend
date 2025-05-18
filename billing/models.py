from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from decimal import Decimal

# Base model with timestamps
class TimeStampedModel(models.Model):
    """Abstract base class with created and updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True


# Main Billing Models
class Bill(TimeStampedModel):
    """Main billing model for all types of services"""
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
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('other', 'Other'),
    ]
    
    BILL_TYPES = [
        ('consultation', 'Consultation'),
        ('lab_test', 'Laboratory Test'),
        ('procedure', 'Medical Procedure'),
        ('pharmacy', 'Pharmacy'),
        ('appointment', 'Appointment'),
        ('lab', 'Lab Test'),
        ('other', 'Other Service'),
    ]
    
    # Core fields
    bill_number = models.CharField(max_length=20, unique=True)
    bill_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    bill_type = models.CharField(max_length=20, choices=BILL_TYPES)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    
    # Notes and metadata
    notes = models.TextField(blank=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Relationships - Using strings to avoid circular imports
    patient = models.ForeignKey('users.Patient', on_delete=models.CASCADE, related_name='billing_bills')
    doctor = models.ForeignKey('users.Doctor', on_delete=models.CASCADE, related_name='billing_bills', null=True, blank=True)
    clinic = models.ForeignKey('users.Clinic', on_delete=models.CASCADE, related_name='billing_bills')
    
    # Optional relationships
    appointment = models.OneToOneField('users.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_bill')
    lab_test = models.OneToOneField('labs.LabOrderTest', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_bill')
    lab_order = models.OneToOneField('labs.LabOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_bill')
    # Comment out until pharmacy app is created
    # pharmacy_order = models.OneToOneField('pharmacy.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_bill')
    
    class Meta:
        ordering = ['-bill_date', '-created_at']
        indexes = [
            models.Index(fields=['bill_number']),
            models.Index(fields=['patient', '-bill_date']),
            models.Index(fields=['clinic', '-bill_date']),
            models.Index(fields=['status', '-bill_date']),
        ]
    
    def __str__(self):
        return f"Bill #{self.bill_number} - {self.patient} ({self.get_status_display()})"
    
    @property
    def due_amount(self):
        """Calculate the amount still due"""
        return self.total - self.amount_paid
    
    def calculate_total(self):
        """Calculate total bill amount"""
        self.subtotal = sum(item.total for item in self.items.all())
        self.total = self.subtotal + self.tax - self.discount
        return self.total
    
    def update_status(self):
        """Update payment status based on payments"""
        total_paid = sum(payment.amount for payment in self.payments.all())
        self.amount_paid = total_paid
        
        if total_paid >= self.total:
            self.status = 'paid'
            self.is_paid = True
        elif total_paid > 0:
            self.status = 'partial'
            self.is_paid = False
        else:
            self.status = 'pending'
            self.is_paid = False
        
        return self.status
    
    def save(self, *args, **kwargs):
        # Generate bill number if not provided
        if not self.bill_number:
            # Format: B-YYYYMMDD-XXXX where XXXX is a sequential number
            date_str = timezone.now().strftime('%Y%m%d')
            last_bill = Bill.objects.filter(bill_number__startswith=f'B-{date_str}').order_by('-bill_number').first()
            
            if last_bill:
                last_num = int(last_bill.bill_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
                
            self.bill_number = f'B-{date_str}-{new_num:04d}'
        
        # Calculate totals
        if not self.id:  # Only for new bills
            self.calculate_total()
        
        # Set due date if not provided (default: 15 days from bill date)
        if not self.due_date:
            self.due_date = self.bill_date + timezone.timedelta(days=15)
            
        super().save(*args, **kwargs)


class BillItem(TimeStampedModel):
    """Individual items in a bill"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Optional reference to different item types
    billing_item = models.ForeignKey('BillingItem', on_delete=models.PROTECT, null=True, blank=True)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.item_name} (x{self.quantity}) - ₹{self.total}"
    
    def save(self, *args, **kwargs):
        # Calculate total automatically
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Update bill total
        self.bill.calculate_total()
        self.bill.save()


class Payment(TimeStampedModel):
    """Payments made against bills"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=Bill.PAYMENT_METHODS)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Receipt
    receipt_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    receipt_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    
    # Person who recorded payment
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment of ₹{self.amount} for {self.bill.bill_number}"
    
    def save(self, *args, **kwargs):
        # Generate receipt number if not provided
        if not self.receipt_number:
            # Format: R-YYYYMMDD-XXXX where XXXX is a sequential number
            date_str = timezone.now().strftime('%Y%m%d')
            last_receipt = Payment.objects.filter(receipt_number__startswith=f'R-{date_str}').order_by('-receipt_number').first()
            
            if last_receipt:
                last_num = int(last_receipt.receipt_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
                
            self.receipt_number = f'R-{date_str}-{new_num:04d}'
            
        super().save(*args, **kwargs)
        
        # Update bill status
        self.bill.update_status()
        self.bill.save()


class BillingItem(models.Model):
    """Pre-defined billing items that can be added to bills"""
    ITEM_TYPES = [
        ('consultation', 'Consultation'),
        ('procedure', 'Medical Procedure'),
        ('medicine', 'Medicine'),
        ('lab_test', 'Laboratory Test'),
        ('service', 'Service'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    item_code = models.CharField(max_length=20, blank=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    clinic = models.ForeignKey('users.Clinic', on_delete=models.CASCADE, related_name='billing_items')
    is_active = models.BooleanField(default=True)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['item_type', 'name']),
            models.Index(fields=['clinic', 'item_type']),
        ]
    
    def __str__(self):
        return f"{self.name} (₹{self.price})"


class LabTestBilling(TimeStampedModel):
    """Links lab tests to billing system"""
    lab_test = models.OneToOneField('labs.LabOrderTest', on_delete=models.CASCADE, related_name='billing')
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_test_billings')
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_home_collection = models.BooleanField(default=False)
    home_collection_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Commission for external labs
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Billing for {self.lab_test}"
    
    def calculate_final_price(self):
        """Calculate final price after discounts and additional fees"""
        discount_amount = (self.base_price * self.discount_percentage) / Decimal('100.0')
        self.final_price = self.base_price - discount_amount + self.home_collection_fee
        
        if self.commission_percentage > 0:
            self.commission_amount = (self.final_price * self.commission_percentage) / Decimal('100.0')
        
        return self.final_price
    
    def save(self, *args, **kwargs):
        self.calculate_final_price()
        super().save(*args, **kwargs)


class ConsultationBilling(TimeStampedModel):
    """Billing for doctor consultations"""
    appointment = models.OneToOneField('users.Appointment', on_delete=models.CASCADE, related_name='consultation_billing', to_field='id')
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultation_billings')
    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    final_fee = models.DecimalField(max_digits=10, decimal_places=2)
    doctor = models.ForeignKey('users.Doctor', on_delete=models.CASCADE, related_name='consultation_billings', null=True, blank=True)
    emergency_fee_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    # Follow-up visit discount
    is_followup = models.BooleanField(default=False)
    followup_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    followup_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Consultation billing for {self.appointment}"
    
    def calculate_final_fee(self):
        """Calculate final fee after discounts"""
        discount_amount = (self.base_fee * self.discount_percentage) / Decimal('100.0')
        self.final_fee = self.base_fee - discount_amount - self.followup_discount
        return self.final_fee
    
    def save(self, *args, **kwargs):
        self.calculate_final_fee()
        super().save(*args, **kwargs)


class InsuranceClaim(TimeStampedModel):
    """Insurance claims for bills"""
    CLAIM_STATUS = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('partial', 'Partially Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]
    
    bill = models.OneToOneField(Bill, on_delete=models.CASCADE, related_name='insurance_claim')
    patient = models.ForeignKey('users.Patient', on_delete=models.CASCADE, related_name='insurance_claims')
    insurance_provider = models.CharField(max_length=100)
    policy_number = models.CharField(max_length=50)
    claim_number = models.CharField(max_length=50, blank=True)
    claim_date = models.DateField(default=timezone.now)
    
    # Amount details
    claimed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='pending')
    notes = models.TextField(blank=True)
    approval_date = models.DateField(null=True, blank=True)
    claim_status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='pending')
    
    # Documents
    claim_form = models.FileField(upload_to='insurance_claims/', null=True, blank=True)
    supporting_documents = models.FileField(upload_to='insurance_claims/documents/', null=True, blank=True)
    
    class Meta:
        ordering = ['-claim_date']
    
    def __str__(self):
        return f"Insurance claim for {self.bill.bill_number}" 