from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from users.models import UserProfile, Patient, Appointment, Prescription, Doctor, PrescriptionItem, Clinic

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
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'first_name', 'last_name', 'date_of_birth', 
                  'gender','blood_group', 'phone_number', 'email', 'address','pincode', 'clinic', 'created_at', 'updated_at']


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_name',
            'doctor_name',
            'appointment_date',
            'status',
            'reason',
            'created_at'
        ]
    
    def get_patient_name(self, obj):
        try:
            if obj.patient and obj.patient.user:
                return f"{obj.patient.user.first_name} {obj.patient.user.last_name}".strip()
            return "Unknown Patient"
        except AttributeError:
            return "Unknown Patient"
    
    def get_doctor_name(self, obj):
        try:
            if obj.doctor:
                return obj.doctor.name or "Unknown Doctor"
            return "Unknown Doctor"
        except AttributeError:
            return "Unknown Doctor"

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
        fields = ['id', 'user_name', 'specialization', 'clinic', 'medical_council']

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
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'patient_id',
            'first_name',
            'last_name',
            'date_of_birth',    
            'gender',
            'blood_group',
            'phone_number',
            'email',
            'address',
            'pincode',
            'clinic',
            'created_at',
            'updated_at'
        ]

    def create(self, validated_data):
        # Generate a unique patient ID if not provided
        if 'patient_id' not in validated_data:
            # You can implement your own patient ID generation logic
            last_patient = Patient.objects.order_by('-id').first()
            patient_id = f'P{str(last_patient.id + 1).zfill(6)}' if last_patient else 'P000001'
            validated_data['patient_id'] = patient_id
        
        return Patient.objects.create(**validated_data)