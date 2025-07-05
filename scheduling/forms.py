from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from django.apps import apps
from .models import AppointmentSchedule, Holiday, ScheduledAppointment, AppointmentType
from users.models import Doctor, Patient, Clinic, Appointment

class AppointmentForm(forms.ModelForm):
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
        initial=timezone.now().date
    )
    appointment_time = forms.TimeField(
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
        required=False  # We'll handle this with available slots
    )
    appointment_type = forms.ModelChoiceField(
        queryset=AppointmentType.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
        empty_label="-- Select Appointment Type --"
    )
    
    # Scheduling-specific fields
    is_telemedicine = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'})
    )
    is_emergency = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-red-600 shadow-sm focus:border-red-300 focus:ring focus:ring-red-200 focus:ring-opacity-50'})
    )
    is_walk_in = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50'})
    )
    
    scheduling_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50',
            'rows': 3,
            'placeholder': 'Additional scheduling notes...'
        })
    )

    class Meta:
        model = Appointment  # Use the existing users.Appointment model
        fields = ['doctor', 'patient', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'doctor': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'patient': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'reason': forms.Textarea(attrs={
                'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is a doctor, pre-select and disable the doctor field
        if self.user and hasattr(self.user, 'doctor'):
            self.fields['doctor'].initial = self.user.doctor
            self.fields['doctor'].widget.attrs['disabled'] = True
            self.fields['doctor'].required = False
            
            # Filter patients by doctor's clinic
            if self.user.doctor.clinic:
                self.fields['patient'].queryset = Patient.objects.filter(clinic=self.user.doctor.clinic)
        
        # If editing an existing appointment, populate the time slot dropdown and scheduling info
        if self.instance and self.instance.pk:
            if self.instance.appointment_time:
                time_str = self.instance.appointment_time.strftime('%H:%M')
                formatted_time = self.instance.appointment_time.strftime('%I:%M %p')
                self.fields['appointment_time'].widget.choices = [
                    (time_str, formatted_time)
                ]
            
            # Load existing scheduling info if it exists
            try:
                scheduling_info = ScheduledAppointment.objects.get(appointment=self.instance)
                self.fields['appointment_type'].initial = scheduling_info.appointment_type
                self.fields['is_telemedicine'].initial = scheduling_info.is_telemedicine
                self.fields['is_emergency'].initial = scheduling_info.is_emergency
                self.fields['is_walk_in'].initial = scheduling_info.is_walk_in
                self.fields['scheduling_notes'].initial = scheduling_info.notes
            except ScheduledAppointment.DoesNotExist:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        doctor = cleaned_data.get('doctor')
        
        # If user is a doctor, use that instead of form field
        if self.user and hasattr(self.user, 'doctor'):
            doctor = self.user.doctor
            cleaned_data['doctor'] = doctor
        
        if appointment_date and appointment_date < timezone.now().date():
            self.add_error('appointment_date', 'Cannot schedule appointments in the past.')
        
        if appointment_date and doctor and not appointment_time:
            self.add_error('appointment_time', 'Please select an available time slot.')
        
        # Check for conflicting appointments
        if appointment_date and appointment_time and doctor:
            conflicts = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=['scheduled', 'confirmed']
            )
            
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            
            if conflicts.exists():
                self.add_error('appointment_time', 'This time slot is already booked.')
        
        return cleaned_data
    
    def save(self, commit=True):
        # Save the main appointment first
        appointment = super().save(commit=False)
        
        if commit:
            appointment.save()
            
            # Create or update scheduling info
            scheduling_info, created = ScheduledAppointment.objects.get_or_create(
                appointment=appointment,
                defaults={
                    'appointment_type': self.cleaned_data.get('appointment_type'),
                    'is_telemedicine': self.cleaned_data.get('is_telemedicine', False),
                    'is_emergency': self.cleaned_data.get('is_emergency', False),
                    'is_walk_in': self.cleaned_data.get('is_walk_in', False),
                    'notes': self.cleaned_data.get('scheduling_notes', ''),
                    'created_by': self.user if self.user else None,
                }
            )
            
            if not created:
                # Update existing scheduling info
                scheduling_info.appointment_type = self.cleaned_data.get('appointment_type')
                scheduling_info.is_telemedicine = self.cleaned_data.get('is_telemedicine', False)
                scheduling_info.is_emergency = self.cleaned_data.get('is_emergency', False)
                scheduling_info.is_walk_in = self.cleaned_data.get('is_walk_in', False)
                scheduling_info.notes = self.cleaned_data.get('scheduling_notes', '')
                scheduling_info.save()
        
        return appointment

class AppointmentScheduleForm(forms.ModelForm):
    class Meta:
        model = AppointmentSchedule
        fields = ['day_of_week', 'start_time', 'end_time', 'break_start_time', 'break_end_time', 'appointment_duration', 'is_active']
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'break_start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'break_end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'appointment_duration': forms.NumberInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'min': '5', 'max': '240'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'}),
        }

class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ['name', 'date', 'description', 'is_clinic_holiday']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'description': forms.Textarea(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'rows': 3}),
            'is_clinic_holiday': forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'}),
        }

class AppointmentTypeForm(forms.ModelForm):
    class Meta:
        model = AppointmentType
        fields = ['name', 'duration', 'color', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'duration': forms.NumberInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'min': '5', 'max': '480'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'h-10 w-20 rounded border border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'description': forms.Textarea(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'}),
        } 