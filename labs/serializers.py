from rest_framework import serializers
from .models import (
    LabProfile,
    TestDefinition,
    LabTestOffering,
    ExternalLabTestOffering,
    LabOrder,
    LabOrderTest,
    LabResult,
    CommissionRule,
    CommissionLedger
)
from users.models import Doctor, Patient, Lab

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

class LabProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = LabProfile
        fields = [
            'id', 
            'name', 
            'lab_id', 
            'registration_number',
            'contact_person', 
            'contact_person_designation',
            'address', 
            'phone_number', 
            'email',
            'accreditation_details',
            'certifications',
            'logo_url',
            'is_approved'
        ]
    
    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

class TestDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestDefinition
        fields = [
            'id', 
            'name', 
            'short_code',
            'description',
            'category',
            'preparation_instructions'
        ]

class LabTestOfferingSerializer(serializers.ModelSerializer):
    lab = serializers.SerializerMethodField()
    test = TestDefinitionSerializer()
    
    class Meta:
        model = LabTestOffering
        fields = [
            'id',
            'lab',
            'test',
            'price',
            'turnaround_time_hours',
            'offers_home_collection',
            'specific_instructions',
            'is_active'
        ]
    
    def get_lab(self, obj):
        return {
            'id': obj.lab.id,
            'name': obj.lab.name
        }

class ExternalLabTestOfferingSerializer(serializers.ModelSerializer):
    lab_profile = LabProfileSerializer()
    test = TestDefinitionSerializer()
    
    class Meta:
        model = ExternalLabTestOffering
        fields = [
            'id',
            'lab_profile',
            'test',
            'price',
            'turnaround_time_hours',
            'offers_home_collection',
            'specific_instructions',
            'is_active'
        ]

class LabOrderTestSerializer(serializers.ModelSerializer):
    test = TestDefinitionSerializer()
    
    class Meta:
        model = LabOrderTest
        fields = [
            'id',
            'test',
            'price',
            'status',
            'created_at',
            'updated_at'
        ]

class LabResultSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_lab = LabProfileSerializer()
    uploaded_by_user = serializers.SerializerMethodField()
    
    class Meta:
        model = LabResult
        fields = [
            'id',
            'file_url',
            'structured_result',
            'uploaded_at',
            'uploaded_by_lab',
            'uploaded_by_user',
            'file_hash',
            'lab_metadata'
        ]
    
    def get_file_url(self, obj):
        if obj.result_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.result_file.url)
            return obj.result_file.url
        return None
    
    def get_uploaded_by_user(self, obj):
        if obj.uploaded_by_user:
            return {
                'id': obj.uploaded_by_user.id,
                'name': f"{obj.uploaded_by_user.first_name} {obj.uploaded_by_user.last_name}"
            }
        return None

class LabOrderSerializer(serializers.ModelSerializer):
    patient = PatientSerializer()
    doctor = DoctorSerializer()
    doctor_recommendation = LabProfileSerializer()
    chosen_lab = LabProfileSerializer()
    tests = TestDefinitionSerializer(many=True)
    order_tests = LabOrderTestSerializer(many=True)
    result = LabResultSerializer()
    
    class Meta:
        model = LabOrder
        fields = [
            'id',
            'patient',
            'doctor',
            'tests',
            'status',
            'doctor_recommendation',
            'chosen_lab',
            'order_date',
            'last_updated',
            'payment_status',
            'total_price',
            'order_tests',
            'result'
        ]

class CommissionRuleSerializer(serializers.ModelSerializer):
    lab = LabProfileSerializer()
    
    class Meta:
        model = CommissionRule
        fields = [
            'id',
            'lab',
            'doctor_percentage',
            'platform_percentage',
            'is_active'
        ]

class CommissionLedgerSerializer(serializers.ModelSerializer):
    order = LabOrderSerializer()
    user = serializers.SerializerMethodField()
    rule_used = CommissionRuleSerializer()
    
    class Meta:
        model = CommissionLedger
        fields = [
            'id',
            'order',
            'user',
            'amount',
            'rule_used',
            'transaction_type',
            'status',
            'created_at',
            'paid_at'
        ]
    
    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'name': f"{obj.user.first_name} {obj.user.last_name}",
            'email': obj.user.email
        }

class LabResultUploadSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(write_only=True)
    result_file = serializers.FileField()
    lab_metadata = serializers.JSONField(required=False)

    def validate_order_id(self, value):
        try:
            order = LabOrder.objects.get(id=value)
            if order.status not in ['PENDING_LAB', 'PROCESSING']:
                raise serializers.ValidationError("This order is not in a state that allows result upload.")
            return value
        except LabOrder.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

    def create(self, validated_data):
        order = LabOrder.objects.get(id=validated_data['order_id'])
        lab = self.context['request'].user.lab_profile
        
        # Create or update LabResult
        result, created = LabResult.objects.update_or_create(
            order=order,
            defaults={
                'result_file': validated_data['result_file'],
                'lab_metadata': validated_data.get('lab_metadata'),
                'uploaded_by_lab': lab
            }
        )
        
        # Update order status
        order.status = 'RESULT_UPLOADED'
        order.save()
        
        return result 