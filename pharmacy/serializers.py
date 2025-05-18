from rest_framework import serializers
from .models import (
    Pharmacy, 
    PharmacyStaff, 
    PharmacyStock, 
    Prescription, 
    PrescriptionDrug,
    Dispensing,
    StockReceipt,
    StockReceiptItem,
    Product,
    ProductStock,
    OTCSale,
    BillHeader,
    BillItem,
    Payment
)
from users.models import Doctor, Patient, Drug

class DoctorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty']
    
    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

class PatientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = ['id', 'name']
    
    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

class DrugSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drug
        fields = ['id', 'product_name', 'generic_name', 'form', 'manufacturer']

class PrescriptionDrugSerializer(serializers.ModelSerializer):
    drug = DrugSerializer()
    dispensed_quantity = serializers.SerializerMethodField()
    remaining_quantity = serializers.SerializerMethodField()
    is_fully_dispensed = serializers.SerializerMethodField()
    
    class Meta:
        model = PrescriptionDrug
        fields = [
            'id', 
            'drug', 
            'dosage_instructions', 
            'quantity', 
            'duration', 
            'dispensed_quantity',
            'remaining_quantity',
            'is_fully_dispensed'
        ]
    
    def get_dispensed_quantity(self, obj):
        return obj.dispensed_quantity
    
    def get_remaining_quantity(self, obj):
        return obj.remaining_quantity
    
    def get_is_fully_dispensed(self, obj):
        return obj.is_fully_dispensed

class DispensingSerializer(serializers.ModelSerializer):
    dispensed_by = serializers.SerializerMethodField()
    
    class Meta:
        model = Dispensing
        fields = [
            'id',
            'quantity',
            'batch_number_dispensed', 
            'dispensed_price_per_unit',
            'total_dispensed_price',
            'dispensed_by',
            'dispensed_at',
            'notes'
        ]
    
    def get_dispensed_by(self, obj):
        return f"{obj.dispensed_by.first_name} {obj.dispensed_by.last_name}" if obj.dispensed_by else ""

class PrescriptionSerializer(serializers.ModelSerializer):
    patient = PatientSerializer()
    doctor = DoctorSerializer()
    prescription_drugs = PrescriptionDrugSerializer(many=True)
    is_expired = serializers.BooleanField()
    
    class Meta:
        model = Prescription
        fields = [
            'id', 
            'patient', 
            'doctor', 
            'status', 
            'created_at', 
            'updated_at', 
            'expiry_date', 
            'notes', 
            'prescription_drugs',
            'is_expired'
        ]

class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'name',
            'address',
            'phone',
            'email',
            'website',
            'is_active'
        ]

class PharmacyStaffSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    pharmacy = PharmacySerializer()
    role_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PharmacyStaff
        fields = [
            'id',
            'user',
            'pharmacy',
            'role',
            'role_display',
            'is_manager',
            'license_number'
        ]
    
    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'name': f"{obj.user.first_name} {obj.user.last_name}",
            'email': obj.user.email
        }
    
    def get_role_display(self, obj):
        return obj.get_role_display()

class PharmacyStockSerializer(serializers.ModelSerializer):
    medicine = DrugSerializer()
    pharmacy = PharmacySerializer()
    is_low_stock = serializers.BooleanField()
    is_expired = serializers.BooleanField()
    stock_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        model = PharmacyStock
        fields = [
            'id',
            'pharmacy',
            'medicine',
            'quantity',
            'batch_number',
            'expiry_date',
            'unit_price',
            'min_stock_level',
            'is_low_stock',
            'is_expired',
            'stock_value'
        ]

class StockReceiptItemSerializer(serializers.ModelSerializer):
    drug = DrugSerializer()
    
    class Meta:
        model = StockReceiptItem
        fields = [
            'id',
            'drug',
            'quantity',
            'batch_number',
            'date_of_manufacture',
            'date_of_expiry',
            'purchase_price_per_unit',
            'total_purchase_price'
        ]

class StockReceiptSerializer(serializers.ModelSerializer):
    items = StockReceiptItemSerializer(many=True)
    pharmacy = PharmacySerializer()
    created_by = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        model = StockReceipt
        fields = [
            'id',
            'pharmacy',
            'receipt_number',
            'supplier_name',
            'supplier_invoice',
            'receipt_date',
            'status',
            'status_display',
            'notes',
            'created_by',
            'created_at',
            'items',
            'total_amount'
        ]
    
    def get_created_by(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'name': f"{obj.created_by.first_name} {obj.created_by.last_name}"
            }
        return None
    
    def get_status_display(self, obj):
        return obj.get_status_display()

class ProductSerializer(serializers.ModelSerializer):
    type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'type',
            'type_display',
            'description',
            'price',
            'is_active'
        ]
    
    def get_type_display(self, obj):
        return obj.get_type_display()

class ProductStockSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    pharmacy = PharmacySerializer()
    is_low_stock = serializers.BooleanField()
    is_expired = serializers.BooleanField()
    
    class Meta:
        model = ProductStock
        fields = [
            'id',
            'pharmacy',
            'product',
            'quantity',
            'batch_number',
            'expiry_date',
            'unit_price',
            'min_stock_level',
            'is_low_stock',
            'is_expired'
        ]

class OTCSaleSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    pharmacy = PharmacySerializer()
    sold_by = serializers.SerializerMethodField()
    
    class Meta:
        model = OTCSale
        fields = [
            'id',
            'pharmacy',
            'product',
            'quantity',
            'sale_price_per_unit',
            'total_sale_price',
            'sold_by',
            'sold_at'
        ]
    
    def get_sold_by(self, obj):
        if obj.sold_by:
            return {
                'id': obj.sold_by.id,
                'name': f"{obj.sold_by.first_name} {obj.sold_by.last_name}"
            }
        return None

class BillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillItem
        fields = [
            'id',
            'item_type',
            'name',
            'description',
            'quantity',
            'price_per_unit',
            'total_price'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    received_by = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'amount',
            'payment_method',
            'payment_method_display',
            'reference_number',
            'payment_date',
            'received_by',
            'notes'
        ]
    
    def get_received_by(self, obj):
        if obj.received_by:
            return {
                'id': obj.received_by.id,
                'name': f"{obj.received_by.first_name} {obj.received_by.last_name}"
            }
        return None
    
    def get_payment_method_display(self, obj):
        return obj.get_payment_method_display()

class BillHeaderSerializer(serializers.ModelSerializer):
    patient = PatientSerializer()
    pharmacy = PharmacySerializer()
    items = BillItemSerializer(many=True)
    payments = PaymentSerializer(many=True)
    status_display = serializers.SerializerMethodField()
    due_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_fully_paid = serializers.BooleanField()
    
    class Meta:
        model = BillHeader
        fields = [
            'id',
            'patient',
            'pharmacy',
            'bill_number',
            'bill_date',
            'status',
            'status_display',
            'total_amount',
            'paid_amount',
            'due_amount',
            'is_fully_paid',
            'notes',
            'items',
            'payments'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display() 