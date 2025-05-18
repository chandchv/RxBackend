from django import forms
from django.utils import timezone

from .models import (
    Bill, BillItem, Payment, 
    InsuranceClaim, LabTestBilling, ConsultationBilling
)
from users.models import Patient


class BillForm(forms.ModelForm):
    """Form for creating and editing bills"""
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )
    
    class Meta:
        model = Bill
        fields = [
            'patient', 'bill_number', 'bill_date', 'due_date', 
            'subtotal', 'tax', 'discount', 'total', 'notes', 'status'
        ]
        widgets = {
            'bill_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'bill_number': forms.TextInput(attrs={'class': 'form-control'}),
            'subtotal': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'tax': forms.NumberInput(attrs={'class': 'form-control'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control'}),
            'total': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make some fields not required as they'll be calculated
        self.fields['bill_number'].required = False
        self.fields['subtotal'].required = False
        self.fields['total'].required = False
        self.fields['tax'].required = False
        self.fields['discount'].required = False
        # Set default dates
        today = timezone.now().date()
        if not self.instance.pk:  # Only for new instances
            self.fields['bill_date'].initial = today
            self.fields['due_date'].initial = today + timezone.timedelta(days=30)


class BillItemForm(forms.ModelForm):
    """Form for adding items to a bill"""
    class Meta:
        model = BillItem
        fields = ['item_name', 'description', 'quantity', 'unit_price']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class PaymentForm(forms.ModelForm):
    """Form for recording payments"""
    class Meta:
        model = Payment
        fields = ['amount', 'payment_date', 'payment_method', 'reference_number', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default payment date to today
        if not self.instance.pk:  # Only for new instances
            self.fields['payment_date'].initial = timezone.now().date()


class InsuranceClaimForm(forms.ModelForm):
    """Form for submitting insurance claims"""
    class Meta:
        model = InsuranceClaim
        fields = [
            'insurance_provider', 'policy_number', 'claim_number',
            'claimed_amount', 'approved_amount', 'claim_date', 
            'approval_date', 'claim_status', 'notes'
        ]
        widgets = {
            'insurance_provider': forms.TextInput(attrs={'class': 'form-control'}),
            'policy_number': forms.TextInput(attrs={'class': 'form-control'}),
            'claim_number': forms.TextInput(attrs={'class': 'form-control'}),
            'claimed_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'approved_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'claim_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'approval_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'claim_status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default claim date to today
        if not self.instance.pk:  # Only for new instances
            self.fields['claim_date'].initial = timezone.now().date()
            self.fields['approved_amount'].required = False
            self.fields['approval_date'].required = False


class LabTestBillingForm(forms.ModelForm):
    """Form for managing lab test billing settings"""
    class Meta:
        model = LabTestBilling
        fields = [
            'lab_test', 'base_price', 'discount_percentage',
            'home_collection_fee'
        ]
        widgets = {
            'lab_test': forms.Select(attrs={'class': 'form-control select2'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'home_collection_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            
        }


class ConsultationBillingForm(forms.ModelForm):
    """Form for managing consultation billing settings"""
    class Meta:
        model = ConsultationBilling
        fields = [
            'doctor', 'base_fee', 'emergency_fee_multiplier'
        ]
        widgets = {
            'doctor': forms.Select(attrs={'class': 'form-control select2'}),
            'base_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'emergency_fee_multiplier': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': '0.1'}),
        }


class BillingFilterForm(forms.Form):
    """Form for filtering billing records"""
    STATUS_CHOICES = [('', 'All Statuses')] + list(Bill.PAYMENT_STATUS)
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    min_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    max_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search bills...'})
    ) 