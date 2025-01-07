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
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': timezone.now().strftime('%Y-%m-%d')
        })
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Please describe your reason for visit'
        })
    )

    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'reason']
        widgets = {
            'doctor': forms.Select(attrs={'class': 'form-control'})
        }

    def clean_appointment_date(self):
        date = self.cleaned_data['appointment_date']
        if date < timezone.now():
            raise forms.ValidationError("Appointment date cannot be in the past")
        return date
    
    def clean_appointment_time(self):
        time = self.cleaned_data['appointment_time']
        if time < timezone.now().time():
            raise forms.ValidationError("Appointment time cannot be in the past")
        return time


class AppointmentForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        required=True,  # Make it not required as it will be set automatically for patient users
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    appointment_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': timezone.now().strftime('%Y-%m-%d')
        })
    )
    
    appointment_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        })
    )
    
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Please describe the reason for visit'
        })
    )

    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            'status': forms.Select(choices=Appointment.STATUS_CHOICES),
            'reason': forms.Textarea(attrs={'rows': 3}),
            'doctor': forms.Select(attrs={'class': 'form-control'})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields optional initially - we'll handle required validation in the view
        self.fields['doctor'].required = False
        self.fields['patient'].required = True
    def clean_appointment_date(self):
        date = self.cleaned_data['appointment_date']
        if date < timezone.now().date():
            raise forms.ValidationError("Appointment date cannot be in the past")
        return date
    


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