from django import forms
from .models import Patient, Appointment, Doctor
from django.utils import timezone

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 
                 'phone_number', 'email', 'address', 'pincode']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
        }
class AppointmentForm_patient(forms.ModelForm):
    appointment_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
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


class AppointmentForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        required=False,  # Make it not required as it will be set automatically for patient users
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    appointment_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
        })
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Please describe the reason for visit'
        })
    )

    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'reason']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(choices=Appointment.STATUS_CHOICES),
            'reason': forms.Textarea(attrs={'rows': 3}),
            'doctor': forms.Select(attrs={'class': 'form-control'})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields optional initially - we'll handle required validation in the view
        self.fields['doctor'].required = False
        self.fields['patient'].required = False
    def clean_appointment_date(self):
        date = self.cleaned_data['appointment_date']
        if date < timezone.now():
            raise forms.ValidationError("Appointment date cannot be in the past")
        return date
    
    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('appointment_date')
        time = cleaned_data.get('appointment_time')
        
        if date and time:
            # Combine date and time
            from datetime import datetime, time as dt_time
            cleaned_data['appointment_date'] = datetime.combine(date, time)
        
        return cleaned_data

class DoctorForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['name', 'clinic']