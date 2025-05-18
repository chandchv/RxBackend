from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from django.apps import apps
from .models import AppointmentSchedule, Holiday, ScheduledAppointment
from users.models import Doctor, Patient, Clinic

class AppointmentForm(forms.ModelForm):
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
        initial=timezone.now().date
    )
    appointment_time = forms.TimeField(
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
        required=False  # We'll handle this with available slots
    )
    appointment_type = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'})
    )
    
    class Meta:
        model = ScheduledAppointment
        fields = [
            'patient', 'doctor', 'clinic', 'appointment_date', 'appointment_time',
            'reason', 'is_telemedicine', 'is_emergency', 'is_walk_in', 'notes'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'doctor': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'clinic': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'reason': forms.Textarea(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'rows': 3}),
            'is_telemedicine': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 mr-2'}),
            'is_emergency': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 mr-2'}),
            'is_walk_in': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 mr-2'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is a doctor, pre-select and disable the doctor field
        if self.user and hasattr(self.user, 'doctor'):
            self.fields['doctor'].initial = self.user.doctor
            self.fields['doctor'].widget.attrs['disabled'] = True
            self.fields['doctor'].required = False
        
        # If editing an existing appointment, populate the time slot dropdown
        if self.instance and self.instance.pk and self.instance.appointment_time:
            # Format the time for display
            time_str = self.instance.appointment_time.strftime('%H:%M')
            formatted_time = self.instance.appointment_time.strftime('%I:%M %p')
            
            self.fields['appointment_time'].widget.choices = [
                (time_str, formatted_time)
            ]
        
        # Populate appointment types if django-appointment is installed
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                type_choices = [(t.id, f"{t.name} ({t.duration} mins)") for t in AppointmentType.objects.all()]
                type_choices.insert(0, ('', '-- Select Appointment Type --'))
                self.fields['appointment_type'].choices = type_choices
                
                # If editing, try to set initial value
                if self.instance and self.instance.pk and hasattr(self.instance, 'appointment_type_id'):
                    self.fields['appointment_type'].initial = self.instance.appointment_type_id
            except LookupError:
                # The model doesn't exist in the installed app
                self.fields['appointment_type'].choices = [('', '-- Appointment Types Not Available --')]
                self.fields['appointment_type'].widget.attrs['disabled'] = True
    
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        doctor = cleaned_data.get('doctor')
        appointment_type_id = cleaned_data.get('appointment_type')
        
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
            conflicts = ScheduledAppointment.objects.filter(
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
        
        # Handle appointment type if django-appointment is installed
        if apps.is_installed('appointment') and appointment_type_id:
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                try:
                    appointment_type = AppointmentType.objects.get(id=appointment_type_id)
                    
                    # Store the appointment type ID for later use in save()
                    cleaned_data['appointment_type_obj'] = appointment_type
                except AppointmentType.DoesNotExist:
                    self.add_error('appointment_type', 'Invalid appointment type selected.')
            except LookupError:
                # The model doesn't exist in the installed app
                pass
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set appointment type if available
        if hasattr(self, 'cleaned_data') and 'appointment_type_obj' in self.cleaned_data:
            appointment_type = self.cleaned_data['appointment_type_obj']
            
            # Store the appointment type ID
            instance.appointment_type_id = appointment_type.id
            
            # If reason is empty, use the appointment type name as default reason
            if not instance.reason:
                instance.reason = appointment_type.name
        
        if commit:
            instance.save()
        
        return instance

class AppointmentScheduleForm(forms.ModelForm):
    class Meta:
        model = AppointmentSchedule
        fields = [
            'doctor', 'clinic', 'day_of_week', 'start_time', 'end_time',
            'break_start_time', 'break_end_time', 'appointment_duration', 'is_active'
        ]
        widgets = {
            'doctor': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'clinic': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'day_of_week': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'break_start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'break_end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'appointment_duration': forms.NumberInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 mr-2'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is a doctor, pre-select and disable the doctor field
        if self.user and hasattr(self.user, 'doctor'):
            self.fields['doctor'].initial = self.user.doctor
            self.fields['doctor'].widget.attrs['disabled'] = True
            self.fields['doctor'].required = False
            
            # Also pre-select the clinic
            self.fields['clinic'].initial = self.user.doctor.clinic
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        break_start_time = cleaned_data.get('break_start_time')
        break_end_time = cleaned_data.get('break_end_time')
        
        # If user is a doctor, use that instead of form field
        if self.user and hasattr(self.user, 'doctor'):
            cleaned_data['doctor'] = self.user.doctor
        
        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', 'End time must be after start time.')
        
        if break_start_time and break_end_time and break_start_time >= break_end_time:
            self.add_error('break_end_time', 'Break end time must be after break start time.')
        
        if break_start_time and not break_end_time:
            self.add_error('break_end_time', 'Break end time is required if break start time is provided.')
        
        if break_end_time and not break_start_time:
            self.add_error('break_start_time', 'Break start time is required if break end time is provided.')
        
        return cleaned_data

class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = [
            'name', 'date', 'description', 'clinic', 'doctor', 'is_clinic_holiday'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'description': forms.Textarea(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50', 'rows': 3}),
            'clinic': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'doctor': forms.Select(attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50'}),
            'is_clinic_holiday': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 mr-2'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        clinic = cleaned_data.get('clinic')
        doctor = cleaned_data.get('doctor')
        is_clinic_holiday = cleaned_data.get('is_clinic_holiday')
        
        if is_clinic_holiday and not clinic:
            self.add_error('clinic', 'Clinic is required for clinic holidays.')
        
        if not is_clinic_holiday and not doctor:
            self.add_error('doctor', 'Doctor is required for non-clinic holidays.')
        
        return cleaned_data 