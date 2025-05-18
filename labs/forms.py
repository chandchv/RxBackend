from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import LabOrder, LabProfile, LabTestOffering, TestDefinition, ExternalLabTestOffering, LabResult
from django.apps import apps
from users.models import Patient

User = get_user_model()

class LabRegistrationForm(UserCreationForm):
    name = forms.CharField(max_length=100)
    registration_number = forms.CharField(
        max_length=50, 
        required=False,
        help_text="Lab's official registration/license number (optional)"
    )
    contact_person = forms.CharField(max_length=255, help_text="Name of the primary contact person")
    contact_person_designation = forms.CharField(max_length=100, help_text="Designation of the contact person")
    address = forms.CharField(widget=forms.Textarea)
    phone_number = forms.CharField(max_length=15)
    email = forms.EmailField()
    certifications = forms.MultipleChoiceField(
        choices=[
            ('ISO', 'ISO Certification'),
            ('NABL', 'NABL Accreditation'),
            ('CAP', 'CAP Accreditation'),
            ('CLIA', 'CLIA Certification'),
            ('JCI', 'JCI Accreditation'),
            ('OTHER', 'Other Certification'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    other_certification = forms.CharField(
        max_length=255,
        required=False,
        help_text="If you selected 'Other Certification', please specify"
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'name', 'registration_number', 
                 'contact_person', 'contact_person_designation', 'address', 'phone_number', 
                 'certifications', 'other_certification')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email

    def clean_registration_number(self):
        registration_number = self.cleaned_data.get('registration_number')
        if registration_number:  # Only validate if registration number is provided
            if LabProfile.objects.filter(registration_number=registration_number).exists():
                raise forms.ValidationError('This registration number is already in use.')
        return registration_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            certifications = self.cleaned_data['certifications']
            if self.cleaned_data['other_certification']:
                certifications.append(self.cleaned_data['other_certification'])
            
            LabProfile.objects.create(
                user=user,
                name=self.cleaned_data['name'],
                registration_number=self.cleaned_data['registration_number'],
                contact_person=self.cleaned_data['contact_person'],
                contact_person_designation=self.cleaned_data['contact_person_designation'],
                address=self.cleaned_data['address'],
                phone_number=self.cleaned_data['phone_number'],
                email=self.cleaned_data['email'],
                certifications=certifications
            )
        return user

class LabTestOfferingForm(forms.ModelForm):
    test = forms.ModelChoiceField(
        queryset=TestDefinition.objects.all(),
        empty_label="Select a test"
    )
    price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        help_text="Price in Indian Rupees (₹)"
    )
    turnaround_time_hours = forms.IntegerField(
        min_value=1,
        help_text="Estimated time to complete the test in hours"
    )
    offers_home_collection = forms.BooleanField(
        required=False,
        help_text="Check if this test can be collected from patient's home"
    )
    specific_instructions = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Specific instructions for the test"
    )

    class Meta:
        model = LabTestOffering
        fields = ['test', 'price', 'turnaround_time_hours', 'offers_home_collection', 'specific_instructions']
        widgets = {
            'test': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'turnaround_time_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'specific_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ExternalLabTestOfferingForm(forms.ModelForm):
    test = forms.ModelChoiceField(
        queryset=TestDefinition.objects.all(),
        empty_label="Select a test"
    )
    price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        help_text="Price in Indian Rupees (₹)"
    )
    turnaround_time_hours = forms.IntegerField(
        min_value=1,
        help_text="Estimated time to complete the test in hours"
    )
    offers_home_collection = forms.BooleanField(
        required=False,
        help_text="Check if this test can be collected from patient's home"
    )
    specific_instructions = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Specific instructions for the test",
        required=False
    )
    lab_profile = forms.ModelChoiceField(
        queryset=LabProfile.objects.filter(is_approved=True),
        required=False,
        help_text="Select the lab (for superusers only)",
        empty_label="Select a lab"
    )

    class Meta:
        model = ExternalLabTestOffering
        fields = ['test', 'price', 'turnaround_time_hours', 'offers_home_collection', 'specific_instructions', 'lab_profile']
        widgets = {
            'test': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'turnaround_time_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'specific_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'lab_profile': forms.Select(attrs={'class': 'form-control'})
        }

class SampleCollectionForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        help_text="Add any notes about the sample collection process"
    )

class LabResultForm(forms.ModelForm):
    class Meta:
        model = LabResult
        fields = ['result_file', 'lab_metadata']
        widgets = {
            'result_file': forms.FileInput(attrs={'class': 'form-control'}),
            'lab_metadata': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        help_texts = {
            'result_file': 'Upload the test result file (PDF, image, or document)',
            'lab_metadata': 'Add any additional notes or metadata about the test result (e.g., Lab Name, Technician, Test Method)'
        } 

class LabOrderForm(forms.ModelForm):
    # Fields for walk-in patient information
    patient_name = forms.CharField(max_length=100, required=True)
    patient_phone = forms.CharField(max_length=15, required=True)
    patient_email = forms.EmailField(required=False)
    patient_age = forms.IntegerField(required=True)
    patient_gender = forms.ChoiceField(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], required=True)
    
    # Multiple test selection
    tests = forms.ModelMultipleChoiceField(
        queryset=TestDefinition.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = LabOrder
        fields = ['patient_name', 'patient_phone', 'patient_email', 'patient_age', 'patient_gender', 'tests']

    def save(self, commit=True):
        # First create or get the patient
        patient, created = Patient.objects.get_or_create(
            phone_number=self.cleaned_data['patient_phone'],
            defaults={
                'first_name': self.cleaned_data['patient_name'].split()[0],
                'last_name': ' '.join(self.cleaned_data['patient_name'].split()[1:]) if len(self.cleaned_data['patient_name'].split()) > 1 else '',
                'email': self.cleaned_data['patient_email'],
                'age': self.cleaned_data['patient_age'],
                'gender': self.cleaned_data['patient_gender']
            }
        )
        
        # Create the lab order
        instance = super().save(commit=False)
        instance.patient = patient
        
        if commit:
            instance.save()
        
        return instance

