from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from users.models import Clinic, Doctor, Drug, Patient
# Create your models here.
class PharmacyUserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacy_user'
    )
    
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.name 
    class Meta:
        abstract = True

class Pharmacy(models.Model):
    """Pharmacy entity representing a physical or virtual pharmacy location"""
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)
    website = models.URLField(max_length=255, blank=True, null=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='pharmacies')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pharmacy"
        verbose_name_plural = "Pharmacies"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class PharmacyStaff(models.Model):
    """Staff members working at pharmacies with access to the pharmacy system"""
    ROLE_CHOICES = [
        ('pharmacist', 'Pharmacist'),
        ('assistant', 'Pharmacy Assistant'),
        ('manager', 'Pharmacy Manager'),
        ('intern', 'Pharmacy Intern'),
        ('other', 'Other Staff')
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacy_staff'
    )
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='staff')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_manager = models.BooleanField(default=False)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pharmacy Staff"
        verbose_name_plural = "Pharmacy Staff"
        ordering = ['pharmacy', 'user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.pharmacy.name} ({self.get_role_display()})"

class PharmacyStock(models.Model):
    """Inventory of medication in a pharmacy"""
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='stock')
    medicine = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='pharmacy_stock')
    quantity = models.PositiveIntegerField(default=0)
    batch_number = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    min_stock_level = models.PositiveIntegerField(default=10, help_text="Minimum stock level before alert")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pharmacy Stock"
        verbose_name_plural = "Pharmacy Stock"
        ordering = ['pharmacy', 'medicine__product_name']
        # Ensure no duplicate medicine batch combinations for a pharmacy
        unique_together = ('pharmacy', 'medicine', 'batch_number')

    def __str__(self):
        return f"{self.pharmacy.name} - {self.medicine.product_name} (Qty: {self.quantity})"
    
    @property
    def is_low_stock(self):
        """Check if stock is below minimum level"""
        return self.quantity <= self.min_stock_level
    
    @property
    def is_expired(self):
        """Check if stock is expired"""
        if self.expiry_date:
            return self.expiry_date <= timezone.now().date()
        return False
    
    @property
    def stock_value(self):
        """Calculate the total value of this stock"""
        return self.quantity * self.unit_price

class Prescription(models.Model):
    """Medical prescription issued by a doctor for a patient"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('processing', 'Processing'),
        ('partially_dispensed', 'Partially Dispensed'),
        ('fully_dispensed', 'Fully Dispensed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pharmacy_prescriptions')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='pharmacy_prescriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField(blank=True, null=True, help_text="Date prescription becomes invalid")
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Prescription"
        verbose_name_plural = "Prescriptions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Prescription #{self.id} - {self.patient.get_full_name()} ({self.created_at.strftime('%Y-%m-%d')})"
    
    @property
    def is_expired(self):
        """Check if prescription has expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        # Default expiry is 6 months if not specified
        return (self.created_at.date() + timezone.timedelta(days=180)) < timezone.now().date()
    
    def update_status(self):
        """Update prescription status based on dispensed drugs"""
        if self.status in ['cancelled', 'expired', 'fully_dispensed']:
            return
        
        # Count prescription drugs and dispensed quantities
        prescription_drugs = self.prescription_drugs.all()
        if not prescription_drugs.exists():
            return
            
        all_dispensed = True
        partially_dispensed = False
        
        for drug in prescription_drugs:
            dispensed_quantity = sum(d.quantity for d in drug.dispensings.all())
            if dispensed_quantity <= 0:
                all_dispensed = False
            elif dispensed_quantity < drug.quantity:
                all_dispensed = False
                partially_dispensed = True
            
        if all_dispensed:
            self.status = 'fully_dispensed'
        elif partially_dispensed:
            self.status = 'partially_dispensed'
        
        self.save(update_fields=['status', 'updated_at'])

class PrescriptionDrug(models.Model):
    """Individual medications within a prescription"""
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='prescription_drugs')
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='prescription_drugs')
    dosage_instructions = models.CharField(max_length=255, blank=True, null=True, 
                                        help_text="E.g., '1 tablet twice daily'")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    duration = models.PositiveIntegerField(default=0, help_text="Duration in days (0 for as needed)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prescription Drug"
        verbose_name_plural = "Prescription Drugs"
        ordering = ['prescription', 'drug__product_name']

    def __str__(self):
        return f"{self.prescription.id} - {self.drug.product_name} (Qty: {self.quantity})"
    
    @property
    def dispensed_quantity(self):
        """Calculate total quantity dispensed"""
        return sum(d.quantity for d in self.dispensings.all())
    
    @property
    def remaining_quantity(self):
        """Calculate quantity yet to be dispensed"""
        return max(0, self.quantity - self.dispensed_quantity)
    
    @property
    def is_fully_dispensed(self):
        """Check if drug has been fully dispensed"""
        return self.dispensed_quantity >= self.quantity

class StockReceipt(models.Model):
    """Header record for stock receipts/purchases"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ]
    
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='stock_receipts')
    receipt_number = models.CharField(max_length=50)
    supplier_name = models.CharField(max_length=255)
    supplier_invoice = models.CharField(max_length=100, blank=True, null=True)
    receipt_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                null=True, related_name='created_stock_receipts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Stock Receipt"
        verbose_name_plural = "Stock Receipts"
        ordering = ['-receipt_date', '-created_at']
    
    def __str__(self):
        return f"Receipt #{self.receipt_number} - {self.pharmacy.name} ({self.receipt_date})"
    
    @property
    def total_amount(self):
        """Calculate total value of receipt"""
        return sum(item.total_purchase_price for item in self.items.all())

class StockReceiptItem(models.Model):
    """Individual items in a stock receipt"""
    receipt = models.ForeignKey(StockReceipt, on_delete=models.CASCADE, related_name='items')
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='stock_receipt_items')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    batch_number = models.CharField(max_length=50, blank=True, null=True)
    date_of_manufacture = models.DateField(blank=True, null=True)
    date_of_expiry = models.DateField()
    purchase_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stock Receipt Item"
        verbose_name_plural = "Stock Receipt Items"
        ordering = ['receipt', 'drug__product_name']

    def __str__(self):
        return f"{self.receipt.receipt_number} - {self.drug.product_name} (Qty: {self.quantity})"
    
    def save(self, *args, **kwargs):
        # Calculate total price if not provided
        if not self.total_purchase_price:
            self.total_purchase_price = self.quantity * self.purchase_price_per_unit
        super().save(*args, **kwargs)

class Dispensing(models.Model):
    """Record of medications dispensed to patients"""
    prescription_drug = models.ForeignKey(PrescriptionDrug, on_delete=models.CASCADE, related_name='dispensings')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='dispensings')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    batch_number_dispensed = models.CharField(max_length=50, blank=True, null=True)
    dispensed_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_dispensed_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    dispensed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                    null=True, related_name='dispensed_medications')
    dispensed_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Dispensing"
        verbose_name_plural = "Dispensings"
        ordering = ['-dispensed_at']
    
    def __str__(self):
        return f"Dispensed {self.quantity} of {self.prescription_drug.drug.product_name} to {self.prescription_drug.prescription.patient.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Calculate total price if not provided
        if not self.total_dispensed_price:
            self.total_dispensed_price = self.quantity * self.dispensed_price_per_unit
        super().save(*args, **kwargs)
        
        # Update prescription status
        self.prescription_drug.prescription.update_status()

class Product(models.Model):
    """Over-the-counter (OTC) products sold in the pharmacy"""
    TYPE_CHOICES = [
        ('injection', 'Injection'),
        ('tablet', 'Tablet'),
        ('syrup', 'Syrup'),
        ('topical', 'Topical'),
        ('device', 'Medical Device'),
        ('supplement', 'Supplement'),
        ('other', 'Other')
    ]
    
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "OTC Product"
        verbose_name_plural = "OTC Products"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class ProductStock(models.Model):
    """Inventory of OTC products in a pharmacy"""
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='product_stock')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.PositiveIntegerField(default=0)
    batch_number = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    min_stock_level = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Product Stock"
        verbose_name_plural = "Product Stock"
        ordering = ['pharmacy', 'product__name']
        unique_together = ('pharmacy', 'product', 'batch_number')
    
    def __str__(self):
        return f"{self.pharmacy.name} - {self.product.name} (Qty: {self.quantity})"
    
    @property
    def is_low_stock(self):
        """Check if stock is below minimum level"""
        return self.quantity <= self.min_stock_level
    
    @property
    def is_expired(self):
        """Check if stock is expired"""
        if self.expiry_date:
            return self.expiry_date <= timezone.now().date()
        return False

class OTCSale(models.Model):
    """Record of OTC product sales"""
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='otc_sales')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    sale_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_sale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                               null=True, related_name='otc_sales')
    sold_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "OTC Sale"
        verbose_name_plural = "OTC Sales"
        ordering = ['-sold_at']
    
    def __str__(self):
        return f"Sold {self.quantity} of {self.product.name} at {self.sold_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Calculate total price if not provided
        if not self.total_sale_price:
            self.total_sale_price = self.quantity * self.sale_price_per_unit
        super().save(*args, **kwargs)

class BillHeader(models.Model):
    """Header record for pharmacy bills"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('finalized', 'Finalized'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pharmacy_bills')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='bills')
    prescription = models.ForeignKey(Prescription, on_delete=models.SET_NULL, 
                                    null=True, blank=True, related_name='bills')
    bill_number = models.CharField(max_length=50, unique=True)
    bill_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                  null=True, related_name='created_pharmacy_bills')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
        ordering = ['-bill_date', '-created_at']
    
    def __str__(self):
        return f"Bill #{self.bill_number} - {self.patient.get_full_name()} ({self.bill_date})"
    
    @property
    def due_amount(self):
        """Calculate amount yet to be paid"""
        return max(0, self.total_amount - self.paid_amount)
    
    @property
    def is_fully_paid(self):
        """Check if bill is fully paid"""
        return self.paid_amount >= self.total_amount
    
    def update_total(self):
        """Update total amount based on bill items"""
        self.total_amount = sum(item.total_price for item in self.items.all())
        self.save(update_fields=['total_amount', 'updated_at'])
    
    def update_status(self):
        """Update bill status based on payment status"""
        if self.status == 'cancelled':
            return
            
        if self.is_fully_paid:
            self.status = 'paid'
        elif self.items.exists():
            self.status = 'finalized'
        else:
            self.status = 'draft'
            
        self.save(update_fields=['status', 'updated_at'])

class BillItem(models.Model):
    """Individual items in a pharmacy bill"""
    ITEM_TYPE_CHOICES = [
        ('prescription', 'Prescription Drug'),
        ('otc', 'OTC Product')
    ]
    
    bill = models.ForeignKey(BillHeader, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    # Optional references to source records
    dispensing = models.OneToOneField(Dispensing, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='bill_item')
    otc_sale = models.OneToOneField(OTCSale, on_delete=models.SET_NULL, 
                                   null=True, blank=True, related_name='bill_item')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Bill Item"
        verbose_name_plural = "Bill Items"
        ordering = ['bill', 'created_at']
    
    def __str__(self):
        return f"{self.name} (Qty: {self.quantity}) - ₹{self.total_price}"
    
    def save(self, *args, **kwargs):
        # Calculate total price if not provided
        if not self.total_price:
            self.total_price = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)
        
        # Update bill total
        self.bill.update_total()

class Payment(models.Model):
    """Payments made against pharmacy bills"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('insurance', 'Insurance'),
        ('other', 'Other')
    ]
    
    bill = models.ForeignKey(BillHeader, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                   null=True, related_name='received_payments')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment of ₹{self.amount} for Bill #{self.bill.bill_number}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Update bill's paid amount and status
        bill = self.bill
        bill.paid_amount = sum(payment.amount for payment in bill.payments.all())
        bill.save(update_fields=['paid_amount', 'updated_at'])
        bill.update_status()
