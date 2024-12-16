from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from users.models import UserProfile, Patient, Appointment, Prescription, Doctor

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
    class Meta:
        model = Patient
        fields = ['id', 'first_name', 'last_name', 'date_of_birth', 'gender', 'phone_number', 'email', 'address', 'pincode']


class AppointmentSerializer(serializers.ModelSerializer):
    patient = PatientSerializer()
    
    class Meta:
        model = Appointment
        fields = ['id', 'patient', 'appointment_date', 'reason', 'status']

class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ['patient', 'doctor', 'date', 'medication', 'dosage', 'instructions']

class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['license_number', 'medical_council', 'specialization']
