import datetime
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from users.models import UserProfile, Patient, Appointment, Prescription, Doctor, PrescriptionItem, Clinic, LabTest, LabTechnician, Lab, LabStaff, Staff, Billing

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'auth_provider', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'is_staff', 'is_superuser']
        extra_kwargs = {
            'password': {'write_only': True}
        }

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')
    username = serializers.CharField(source='user.username')

    class Meta:
        model = UserProfile
        fields = ['username', 'first_name', 'last_name', 'email', 'title', 
                 'medical_degree', 'license_number', 'state_council', 
                 'phone_number', 'address', 'pincode']


class PatientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'first_name', 'last_name', 'date_of_birth', 
                  'gender','blood_group', 'phone_number', 'email', 'address','pincode', 'clinic', 'created_at', 'updated_at', 'age']
    
    def get_age(self, obj):
        return obj.get_age()


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    patient = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient',
            'doctor',
            'patient_name',
            'doctor_name',
            'appointment_date',
            'appointment_time',
            'status',
            'reason',
            'created_at'
        ]
    
    def get_patient_name(self, obj):
        try:
            if obj.patient:
                return f"{obj.patient.first_name} {obj.patient.last_name}".strip()
            return "Unknown Patient"
        except AttributeError:
            return "Unknown Patient"
    
    def get_doctor_name(self, obj):
        try:
            if obj.doctor:
                return f"Dr. {obj.doctor.user.first_name} {obj.doctor.user.last_name}".strip()
            return "Unknown Doctor"
        except AttributeError:
            return "Unknown Doctor"
    
    def get_patient(self, obj):
        """Return patient details for React Native app"""
        try:
            if obj.patient:
                return {
                    'id': obj.patient.id,
                    'first_name': obj.patient.first_name,
                    'last_name': obj.patient.last_name,
                    'email': obj.patient.email,
                    'phone_number': obj.patient.phone_number
                }
            return None
        except AttributeError:
            return None

    def validate_appointment_date(self, value):
        """
        Validate the appointment date format and ensure it's not in the past
        """
        if value < datetime.datetime.now():
            raise serializers.ValidationError("Appointment date cannot be in the past")
        return value

    def create(self, validated_data):
        # Add any additional logic needed for appointment creation
        return Appointment.objects.create(**validated_data)

class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ['medicine', 'dosage', 'duration', 'duration_unit', 'instructions']

class PrescriptionSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    items = PrescriptionItemSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    
    class Meta:
        model = Prescription
        fields = [
            'id', 
            'doctor_name',
            'chief_complaints',
            'clinical_findings', 
            'diagnosis',
            'advice',
            'date',
            'follow_up_date',
            'created_at',
            'updated_at',
            'items'  # This will include the prescription items
        ]

class DoctorSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Doctor
        fields = ['id', 'user_name', 'specialization', 'clinic', 'medical_council', 'license_number']

class DoctorSerializer1(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = [
            'id',
            'name',
            'specialization',
            'license_number',
            'email',
            'phone',
            'status',
            'consultation_fee',
            'profile_picture',
            'clinic'
        ]
class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = [
            'id',
            'name',
            'address',
            'phone_number',
            'email',
            'registration_number',
            'logo'
        ]

class PatientListSerializer(serializers.ModelSerializer):
    assigned_doctor = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    gender_display = serializers.CharField(source='get_gender_display')

    class Meta:
        model = Patient
        fields = [
            'id', 
            'patient_id',
            'first_name', 
            'last_name',
            'email',
            'phone_number',
            'address',
            'gender_display',
            'age',
            'blood_group',
            'assigned_doctor',
            'pincode'
        ]

    def get_assigned_doctor(self, obj):
        if obj.doctor:
            return f"Dr. {obj.doctor.name}"
        return None

    def get_age(self, obj):
        return obj.get_age()

class MedicalHistorySerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_name', 'doctor_name', 'appointment', 'diagnosis', 'treatment', 'created_at']

class ClinicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = [
            'clinic_name',
            'address',
            'phone',
            'email',
            'working_hours',
            'appointment_duration',
            'break_duration',
            'online_booking',
            'sms_reminders',
            'email_notifications',
            'logo'
        ]
    
class PatientDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'first_name', 'last_name', 'date_of_birth', 'gender', 'blood_group', 'phone_number', 'email', 'address', 'pincode', 'clinic', 'created_at', 'updated_at']

class LabTestSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    
    class Meta:
        model = LabTest
        fields = '__all__'

class LabTechnicianSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = LabTechnician
        fields = '__all__'

class LabSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = '__all__'

class LabStaffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email')
    
    class Meta:
        model = LabStaff
        fields = ['id', 'user_name', 'email', 'role', 'specialization', 'lab', 'is_active']

class StaffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email')
    phone_number = serializers.CharField(source='user.userprofile.phone_number', read_only=True)
    
    class Meta:
        model = Staff
        fields = ['id', 'user_name', 'email', 'phone_number', 'role', 'clinic', 'is_active']

class BillingSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    appointment_date = serializers.DateField(source='appointment.date', read_only=True)
    appointment_time = serializers.TimeField(source='appointment.time', read_only=True)
    doctor_name = serializers.CharField(source='appointment.doctor.get_full_name', read_only=True)

    class Meta:
        model = Billing
        fields = [
            'id',
            'patient',
            'patient_name',
            'appointment',
            'appointment_date',
            'appointment_time',
            'doctor_name',
            'amount',
            'is_paid',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

