from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Patient, Appointment, Doctor, DoctorAvailability, Bill, BillItem, Payment, BillingItem, Clinic, Lab
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
