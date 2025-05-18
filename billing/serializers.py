from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Bill, BillItem, Payment, BillingItem, 
    LabTestBilling, ConsultationBilling, InsuranceClaim
)
from users.models import Patient, Doctor

User = get_user_model()

class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'full_name', 'phone_number', 'email']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'full_name', 'specialization']
    
    def get_full_name(self, obj):
        return obj.name  # assuming name already contains the full name

class BillingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingItem
        fields = ['id', 'name', 'item_code', 'item_type', 'price', 'description', 'is_active', 'tax_percentage']

class BillItemSerializer(serializers.ModelSerializer):
    billing_item_details = BillingItemSerializer(source='billing_item', read_only=True)
    
    class Meta:
        model = BillItem
        fields = ['id', 'item_name', 'description', 'quantity', 'unit_price', 'total', 'billing_item', 'billing_item_details']
        read_only_fields = ['total']

class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = ['id', 'bill', 'amount', 'payment_date', 'payment_method', 'transaction_id', 
                  'notes', 'receipt_number', 'receipt_file', 'recorded_by', 'recorded_by_name']
        read_only_fields = ['receipt_number']
    
    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}"
        return None

class LabTestBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTestBilling
        fields = ['id', 'lab_test', 'bill', 'base_price', 'discount_percentage', 'final_price',
                  'is_home_collection', 'home_collection_fee', 'commission_percentage', 'commission_amount']
        read_only_fields = ['final_price', 'commission_amount']

class ConsultationBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationBilling
        fields = ['id', 'appointment', 'bill', 'base_fee', 'discount_percentage', 'final_fee',
                  'is_followup', 'followup_discount']
        read_only_fields = ['final_fee']

class InsuranceClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceClaim
        fields = ['id', 'bill', 'patient', 'insurance_provider', 'policy_number', 'claim_number',
                  'claim_date', 'claimed_amount', 'approved_amount', 'paid_amount', 'status', 
                  'notes', 'claim_form', 'supporting_documents']
        read_only_fields = ['claim_number']

class BillListSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Bill
        fields = ['id', 'bill_number', 'bill_date', 'due_date', 'bill_type', 'patient', 
                  'patient_name', 'doctor', 'doctor_name', 'total', 'status', 'status_display', 'is_paid']
    
    def get_patient_name(self, obj):
        return obj.patient.get_full_name() if obj.patient else None
    
    def get_doctor_name(self, obj):
        return obj.doctor.name if obj.doctor else None

class BillDetailSerializer(serializers.ModelSerializer):
    items = BillItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    patient_details = PatientSerializer(source='patient', read_only=True)
    doctor_details = DoctorSerializer(source='doctor', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    bill_type_display = serializers.CharField(source='get_bill_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    total_paid = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()
    
    class Meta:
        model = Bill
        fields = [
            'id', 'bill_number', 'bill_date', 'due_date', 'bill_type', 'bill_type_display',
            'subtotal', 'tax', 'discount', 'total', 'status', 'status_display', 
            'payment_method', 'payment_method_display', 'is_paid', 'notes', 'reference_id',
            'patient', 'patient_details', 'doctor', 'doctor_details', 'clinic',
            'appointment', 'lab_test', 'items', 'payments', 'total_paid', 'amount_due',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['bill_number', 'subtotal', 'total', 'status', 'is_paid']
    
    def get_total_paid(self, obj):
        return sum(payment.amount for payment in obj.payments.all())
    
    def get_amount_due(self, obj):
        return obj.total - self.get_total_paid(obj)

class BillCreateSerializer(serializers.ModelSerializer):
    items = BillItemSerializer(many=True, required=False)
    
    class Meta:
        model = Bill
        fields = [
            'patient', 'doctor', 'clinic', 'bill_date', 'due_date', 'bill_type',
            'tax', 'discount', 'notes', 'reference_id', 'appointment', 'lab_test', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        bill = Bill.objects.create(**validated_data)
        
        for item_data in items_data:
            BillItem.objects.create(bill=bill, **item_data)
        
        bill.calculate_total()
        bill.save()
        return bill
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        
        # Update the bill instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle bill items if provided
        if items_data:
            instance.items.all().delete()  # Remove existing items
            for item_data in items_data:
                BillItem.objects.create(bill=instance, **item_data)
        
        instance.calculate_total()
        instance.save()
        return instance 