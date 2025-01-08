from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Patient, Appointment, Doctor, DoctorAvailability
from django.utils import timezone

class PatientSignupForm(UserCreationForm):
   first_name = forms.CharField(max_length=30, required=True)
   last_name = forms.CharField(max_length=30, required=True)
   email = forms.EmailField(max_length=254, required=True)
   phone_number = forms.CharField(max_length=15, required=True)
   date_of_birth = forms.DateField(
       widget=forms.DateInput(attrs={'type': 'date'}),
       required=True
   )
   gender = forms.ChoiceField(
       choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
       required=True
   )
   address = forms.CharField(
       widget=forms.Textarea(attrs={'rows': 3}),
       required=True
   )
   blood_group = forms.ChoiceField(
       choices=[
           ('A+', 'A+'), ('A-', 'A-'),
           ('B+', 'B+'), ('B-', 'B-'),
           ('O+', 'O+'), ('O-', 'O-'),
           ('AB+', 'AB+'), ('AB-', 'AB-'),
       ],
       required=False
   )
class Meta:
       model = User
       fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 
                 'phone_number', 'email', 'address', 'pincode']
        widgets = {
            'blood_group': forms.Select(choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('O+', 'O+'), ('O-', 'O-'), ('AB+', 'AB+'), ('AB-', 'AB-')]),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
        }
class AppointmentForm_patient(forms.ModelForm):
    appointment_time = forms.TimeField(input_formats=['%H:%M'])
    
    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        
        if appointment_date and appointment_time:
            # Convert to date for comparison
            today = timezone.now().date()
            if appointment_date < today:
                raise forms.ValidationError("Cannot schedule appointments in the past")
        
        return cleaned_data

class AppointmentForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    appointment_time = forms.TimeField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = Appointment
        fields = ['doctor', 'patient', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'appointment_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input w-full rounded-md'
            }),
            'patient': forms.Select(attrs={
                'class': 'form-select w-full rounded-md'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-textarea w-full rounded-md',
                'rows': 3
            }),
            'appointment_time': forms.TimeInput(attrs={
                'class': 'form-time w-full rounded-md',
                'type': 'time'
            })
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            self.fields['doctor'].initial = doctor
            self.fields['patient'].queryset = Patient.objects.filter(clinic=doctor.clinic)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        
        if appointment_date and appointment_time:
            # Convert to date for comparison
            today = timezone.now().date()
            if appointment_date < today:
                raise forms.ValidationError("Cannot schedule appointments in the past")
        
        return cleaned_data

class DoctorForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['name', 'clinic']

class DoctorSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(max_length=254, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    
    # Doctor specific fields
    title = forms.CharField(max_length=50, required=True)
    medical_degree = forms.CharField(max_length=100, required=True)
    license_number = forms.CharField(max_length=50, required=True)
    state_council = forms.CharField(max_length=100, required=True)
    clinic_name = forms.CharField(max_length=100, required=True)
    clinic_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)
    clinic_phone = forms.CharField(max_length=15, required=True)
    specialization = forms.CharField(max_length=100, required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

class DoctorAvailabilityForm(forms.ModelForm):
    class Meta:
        model = DoctorAvailability
        fields = ['day_of_week', 'shift', 'start_time', 'end_time', 'is_available']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

class StaffAppointmentForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select w-full rounded-md',
            'required': True
        })
    )
    appointment_time = forms.TimeField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = Appointment
        fields = ['doctor', 'patient', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'appointment_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input w-full rounded-md'
            }),
            'patient': forms.Select(attrs={
                'class': 'form-select w-full rounded-md'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-textarea w-full rounded-md',
                'rows': 3
            }),
            'appointment_time': forms.TimeInput(attrs={
                'class': 'form-time w-full rounded-md',
                'type': 'time'
            })
        }

    def __init__(self, *args, **kwargs):
        clinic = kwargs.pop('clinic', None)
        super().__init__(*args, **kwargs)
        if clinic:
            self.fields['doctor'].queryset = Doctor.objects.filter(clinic=clinic)
            self.fields['patient'].queryset = Patient.objects.filter(clinic=clinic)
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        return cleaned_data
