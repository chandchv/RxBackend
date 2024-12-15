from django import forms
from .models import Patient, Appointment

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 
                 'phone_number', 'email', 'address']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=[
                ('M', 'Male'),
                ('F', 'Female'),
                ('O', 'Other')
            ])
        }

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'status']
        widgets = {
            'appointment_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'status': forms.Select(choices=Appointment.STATUS_CHOICES)
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the datetime field format compatible with the HTML5 datetime-local input
        if self.instance.pk and self.instance.appointment_date:
            self.initial['appointment_date'] = self.instance.appointment_date.strftime('%Y-%m-%dT%H:%M') 