from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    Patient, Appointment, Doctor, DoctorAvailability, Bill, BillItem, Payment, BillingItem, Clinic, Lab, DoctorLeave, LabRegistration, 
    PatientVitals, Prescription, PrescriptionItem, LabTest, LabTestPrescription
)
from django.utils import timezone
from labs.models import LabProfile, ExternalLabTestOffering, TestDefinition
from django.forms import modelformset_factory, inlineformset_factory, BaseInlineFormSet
from django.core.validators import MinValueValidator, MaxValueValidator

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
    
    # Appointment type fields
    is_emergency = forms.BooleanField(
        required=False,
        label="Emergency Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-red-600'})
    )
    is_telemedicine = forms.BooleanField(
        required=False,
        label="Telemedicine Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600'})
    )
    is_walk_in = forms.BooleanField(
        required=False,
        label="Walk-in Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-green-600'})
    )
    
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
    
    def save(self, commit=True):
        appointment = super().save(commit=False)
        
        if commit:
            appointment.save()
            
            # Create or update scheduling bridge record with appointment types
            from scheduling.models import ScheduledAppointment
            scheduling_info, created = ScheduledAppointment.objects.get_or_create(
                appointment=appointment,
                defaults={
                    'is_emergency': self.cleaned_data.get('is_emergency', False),
                    'is_telemedicine': self.cleaned_data.get('is_telemedicine', False),
                    'is_walk_in': self.cleaned_data.get('is_walk_in', False),
                    'notes': '',
                }
            )
            
            if not created:
                # Update existing scheduling info
                scheduling_info.is_emergency = self.cleaned_data.get('is_emergency', False)
                scheduling_info.is_telemedicine = self.cleaned_data.get('is_telemedicine', False)
                scheduling_info.is_walk_in = self.cleaned_data.get('is_walk_in', False)
                scheduling_info.save()
        
        return appointment

class AppointmentForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    appointment_time = forms.TimeField(required=False, widget=forms.HiddenInput())
    
    # Appointment type fields
    is_emergency = forms.BooleanField(
        required=False,
        label="Emergency Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-red-600'})
    )
    is_telemedicine = forms.BooleanField(
        required=False,
        label="Telemedicine Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600'})
    )
    is_walk_in = forms.BooleanField(
        required=False,
        label="Walk-in Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-green-600'})
    )
    
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
        
        # If editing an existing appointment, populate appointment type fields
        if self.instance and self.instance.pk:
            try:
                from scheduling.models import ScheduledAppointment
                scheduling_info = ScheduledAppointment.objects.get(appointment=self.instance)
                self.fields['is_emergency'].initial = scheduling_info.is_emergency
                self.fields['is_telemedicine'].initial = scheduling_info.is_telemedicine
                self.fields['is_walk_in'].initial = scheduling_info.is_walk_in
            except ScheduledAppointment.DoesNotExist:
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            
            # Create or update scheduling bridge record with appointment types
            from scheduling.models import ScheduledAppointment
            scheduling_info, created = ScheduledAppointment.objects.get_or_create(
                appointment=instance,
                defaults={
                    'is_emergency': self.cleaned_data.get('is_emergency', False),
                    'is_telemedicine': self.cleaned_data.get('is_telemedicine', False),
                    'is_walk_in': self.cleaned_data.get('is_walk_in', False),
                    'notes': '',
                }
            )
            
            if not created:
                # Update existing scheduling info
                scheduling_info.is_emergency = self.cleaned_data.get('is_emergency', False)
                scheduling_info.is_telemedicine = self.cleaned_data.get('is_telemedicine', False)
                scheduling_info.is_walk_in = self.cleaned_data.get('is_walk_in', False)
                scheduling_info.save()
                
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
        fields = ['start_time', 'end_time', 'is_available']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_available'].initial = True
        self.fields['is_available'].widget = forms.HiddenInput()

class StaffAppointmentForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select w-full rounded-md',
            'required': True
        })
    )
    appointment_time = forms.TimeField(required=False, widget=forms.HiddenInput())
    
    # Appointment type fields
    is_emergency = forms.BooleanField(
        required=False,
        label="Emergency Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-red-600'})
    )
    is_telemedicine = forms.BooleanField(
        required=False,
        label="Telemedicine Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-blue-600'})
    )
    is_walk_in = forms.BooleanField(
        required=False,
        label="Walk-in Appointment",
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300 text-green-600'})
    )
    
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
        
        # If editing an existing appointment, populate appointment type fields
        if self.instance and self.instance.pk:
            try:
                from scheduling.models import ScheduledAppointment
                scheduling_info = ScheduledAppointment.objects.get(appointment=self.instance)
                self.fields['is_emergency'].initial = scheduling_info.is_emergency
                self.fields['is_telemedicine'].initial = scheduling_info.is_telemedicine
                self.fields['is_walk_in'].initial = scheduling_info.is_walk_in
            except ScheduledAppointment.DoesNotExist:
                pass
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            
            # Create or update scheduling bridge record with appointment types
            from scheduling.models import ScheduledAppointment
            scheduling_info, created = ScheduledAppointment.objects.get_or_create(
                appointment=instance,
                defaults={
                    'is_emergency': self.cleaned_data.get('is_emergency', False),
                    'is_telemedicine': self.cleaned_data.get('is_telemedicine', False),
                    'is_walk_in': self.cleaned_data.get('is_walk_in', False),
                    'notes': '',
                }
            )
            
            if not created:
                # Update existing scheduling info
                scheduling_info.is_emergency = self.cleaned_data.get('is_emergency', False)
                scheduling_info.is_telemedicine = self.cleaned_data.get('is_telemedicine', False)
                scheduling_info.is_walk_in = self.cleaned_data.get('is_walk_in', False)
                scheduling_info.save()
                
        return instance
        
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        return cleaned_data

class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['due_date', 'discount', 'notes', 'payment_method']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

class BillItemForm(forms.ModelForm):
    class Meta:
        model = BillItem
        fields = ['billing_item', 'quantity']
        
    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic:
            self.fields['billing_item'].queryset = BillingItem.objects.filter(clinic=clinic)

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'payment_date', 'transaction_id', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Username'
            }
        )
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'appearance-none block w-full px-3 py-2 border rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Password',
                'id': 'password'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_messages['invalid_login'] = 'Please enter a correct username and password.'
        
    def is_valid(self):
        valid = super().is_valid()
        if not valid:
            if 'password' in self.errors:
                self.fields['password'].widget.attrs.update({
                    'class': 'appearance-none block w-full px-3 py-2 border border-red-500 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm bg-red-50',
                })
            if 'username' in self.errors:
                self.fields['username'].widget.attrs.update({
                    'class': 'appearance-none block w-full px-3 py-2 border border-red-500 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm bg-red-50',
                })
        return valid

class ClinicProfileForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = [
            'name',
            'address',
            'phone_number',
            'email',
            'logo', 
            'registration_number',
            'website',
            'description',
            'specializations',
            'opening_hours',
            'emergency_contact'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'opening_hours': forms.TextInput(attrs={'placeholder': 'e.g., Mon-Fri: 9AM-6PM'}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = ''.join(filter(str.isdigit, phone))
            if len(phone) < 10 or len(phone) > 15:
                raise forms.ValidationError("Phone number must be between 10 and 15 digits")
        return phone

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Add image validation if needed
            if logo.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("Image file too large ( > 5MB )")
        return logo

class LabForm(forms.ModelForm):
    class Meta:
        model = Lab
        fields = ['name', 'registration_number', 'address', 'phone_number', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class DoctorLeaveForm(forms.ModelForm):
    class Meta:
        model = DoctorLeave
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("End date must be after start date")
            
        return cleaned_data

class LabRegistrationForm(forms.ModelForm):
    class Meta:
        model = LabRegistration
        fields = [
            'name', 'email', 'phone_number', 'address', 'city', 'state', 
            'pincode', 'registration_number', 'gst_number', 'kyc_documents'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_registration_number(self):
        registration_number = self.cleaned_data.get('registration_number')
        if LabRegistration.objects.filter(registration_number=registration_number).exists():
            raise forms.ValidationError("A lab with this registration number already exists.")
        return registration_number

    def clean_gst_number(self):
        gst_number = self.cleaned_data.get('gst_number')
        if LabRegistration.objects.filter(gst_number=gst_number).exists():
            raise forms.ValidationError("A lab with this GST number already exists.")
        return gst_number

# --- Forms for Prescription Creation ---

class VitalsForm(forms.ModelForm):
    weight = forms.FloatField(required=False, validators=[MinValueValidator(0), MaxValueValidator(500)], widget=forms.NumberInput(attrs={'step': '0.1', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))
    height = forms.FloatField(required=False, validators=[MinValueValidator(0), MaxValueValidator(300)], widget=forms.NumberInput(attrs={'step': '0.1', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))
    blood_pressure = forms.CharField(required=False, max_length=20, widget=forms.TextInput(attrs={'placeholder': 'e.g., 120/80', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))
    temperature = forms.FloatField(required=False, validators=[MinValueValidator(90), MaxValueValidator(110)], widget=forms.NumberInput(attrs={'step': '0.1', 'placeholder': '°F', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))
    heart_rate = forms.IntegerField(required=False, validators=[MinValueValidator(0), MaxValueValidator(300)], widget=forms.NumberInput(attrs={'step': '1', 'placeholder': 'bpm', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))
    oxygen_saturation = forms.FloatField(required=False, validators=[MinValueValidator(0), MaxValueValidator(100)], widget=forms.NumberInput(attrs={'step': '0.1', 'placeholder': '%', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}))

    class Meta:
        model = PatientVitals
        fields = ['weight', 'height', 'blood_pressure', 'temperature', 'heart_rate', 'oxygen_saturation']

class PrescriptionForm(forms.ModelForm):
    follow_up_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class':'form-input'}))

    class Meta:
        model = Prescription
        fields = ['chief_complaints', 'clinical_findings', 'diagnosis', 'advice', 'follow_up_date']
        widgets = {
            'chief_complaints': forms.Textarea(attrs={'rows': 4, 'class': 'form-textarea w-full', 'required': True}),
            'clinical_findings': forms.Textarea(attrs={'rows': 4, 'class': 'form-textarea w-full'}),
            'diagnosis': forms.Textarea(attrs={'rows': 2, 'class': 'mt-1 block bg-gray-100 w-full rounded-md border-gray-500 shadow-sm', 'required': True}),
            'advice': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea w-full'}),
        }

class PrescriptionItemForm(forms.ModelForm):
    medicine = forms.CharField(widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'bg-gray-100'})) # Make readonly, set via JS
    dosage = forms.ChoiceField(choices=PrescriptionItem.DOSAGE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    duration = forms.IntegerField(min_value=1, required=True, widget=forms.NumberInput(attrs={'class': 'form-input w-16', 'min': '1'}))
    duration_unit = forms.ChoiceField(choices=PrescriptionItem.DURATION_UNIT_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    instructions = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g., After food', 'class': 'form-input'}))

    class Meta:
        model = PrescriptionItem
        fields = ['medicine', 'dosage', 'duration', 'duration_unit', 'instructions']

# Use inline formset as items are directly related to Prescription
BasePrescriptionItemFormSet = inlineformset_factory(
    Prescription, 
    PrescriptionItem, 
    form=PrescriptionItemForm, 
    extra=0, # Start with 0 extra forms, add dynamically via JS
    can_delete=True
)

class LabTestForm(forms.Form): # Not a ModelForm directly tied to LabTest yet, handle creation in view
    test_name = forms.CharField(max_length=200, required=True, widget=forms.HiddenInput()) # Set via JS
    collection_type = forms.ChoiceField(choices=LabTest.COLLECTION_TYPE, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 1, 'class': 'form-textarea'}))
    lab_id = forms.CharField(required=True, widget=forms.HiddenInput()) # Store combined type-id like 'internal-5' or 'external-12'
    
    # We won't directly map this form to LabTest model saving initially,
    # as we need to handle LabTestPrescription creation and TestDefinition lookup in the view.
    # The 'lab_id' field will store combined info to simplify JS and retrieve lab type/pk in the view.

BaseLabTestFormSet = forms.formset_factory(LabTestForm, extra=0, can_delete=True)

# --- End Forms for Prescription Creation ---
