from django import forms
from .models import Patient, Appointment, Doctor

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 
                 'phone_number', 'email', 'address', 'pincode']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
        }

class AppointmentForm(forms.ModelForm):
    appointment_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True
    )

    class Meta:
        model = Appointment
        fields = ['patient', 'appointment_date', 'reason', 'status']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(choices=Appointment.STATUS_CHOICES),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

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