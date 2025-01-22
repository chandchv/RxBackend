from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from ..models import Bill, BillItem, Payment, BillingItem, Doctor, Patient, Clinic
from ..forms import BillForm, BillItemForm, PaymentForm
import json

# Patient Views
@login_required
def patient_billing_history(request):
    try:
        patient = Patient.objects.get(user=request.user)
        bills = Bill.objects.filter(patient=patient).order_by('-bill_date')
        
        context = {
            'bills': bills,
            'total_pending': sum(bill.total for bill in bills if bill.status == 'pending')
        }
        return render(request, 'billing/patient/billing_history.html', context)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:dashboard')

@login_required
def patient_bill_detail(request, bill_id):
    try:
        patient = Patient.objects.get(user=request.user)
        bill = get_object_or_404(Bill, id=bill_id, patient=patient)
        
        context = {
            'bill': bill,
            'items': bill.items.all(),
            'payments': bill.payments.all()
        }
        return render(request, 'billing/patient/bill_detail.html', context)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found')
        return redirect('users:dashboard')

# Doctor Views
@login_required
def doctor_billing_summary(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        bills = Bill.objects.filter(doctor=doctor).order_by('-bill_date')
        
        # Calculate summary statistics
        total_billed = sum(bill.total for bill in bills)
        total_paid = sum(bill.total for bill in bills if bill.status == 'paid')
        total_pending = sum(bill.total for bill in bills if bill.status == 'pending')
        
        context = {
            'bills': bills,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'total_pending': total_pending
        }
        return render(request, 'billing/doctor/billing_summary.html', context)
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

@login_required
def create_bill(request, appointment_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        if request.method == 'POST':
            form = BillForm(request.POST)
            if form.is_valid():
                bill = form.save(commit=False)
                bill.doctor = doctor
                bill.patient = appointment.patient
                bill.appointment = appointment
                bill.clinic = doctor.clinic
                bill.save()
                
                # Handle bill items
                items_data = json.loads(request.POST.get('items_data', '[]'))
                for item_data in items_data:
                    BillItem.objects.create(
                        bill=bill,
                        billing_item_id=item_data['item_id'],
                        quantity=item_data['quantity'],
                        price=item_data['price']
                    )
                
                messages.success(request, 'Bill created successfully')
                return redirect('users:doctor_billing_summary')
        else:
            form = BillForm()
            
        context = {
            'form': form,
            'appointment': appointment,
            'billing_items': BillingItem.objects.filter(clinic=doctor.clinic),
        }
        return render(request, 'billing/doctor/create_bill.html', context)
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')

# Admin Views
@login_required
def admin_billing_dashboard(request):
    try:
        clinic_admin = ClinicAdmin.objects.get(user=request.user)
        clinic = clinic_admin.clinic
        
        bills = Bill.objects.filter(clinic=clinic).order_by('-bill_date')
        
        # Summary statistics
        total_billed = sum(bill.total for bill in bills)
        total_paid = sum(bill.total for bill in bills if bill.status == 'paid')
        total_pending = sum(bill.total for bill in bills if bill.status == 'pending')
        
        # Monthly statistics
        current_month = timezone.now().month
        monthly_bills = bills.filter(bill_date__month=current_month)
        monthly_total = sum(bill.total for bill in monthly_bills)
        
        context = {
            'bills': bills,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'monthly_total': monthly_total,
            'monthly_bills_count': monthly_bills.count()
        }
        return render(request, 'billing/admin/billing_dashboard.html', context)
    except ClinicAdmin.DoesNotExist:
        messages.error(request, 'Admin profile not found')
        return redirect('users:dashboard')

@login_required
def record_payment(request, bill_id):
    try:
        clinic_admin = ClinicAdmin.objects.get(user=request.user)
        bill = get_object_or_404(Bill, id=bill_id, clinic=clinic_admin.clinic)
        
        if request.method == 'POST':
            form = PaymentForm(request.POST)
            if form.is_valid():
                payment = form.save(commit=False)
                payment.bill = bill
                payment.save()
                
                messages.success(request, 'Payment recorded successfully')
                return redirect('users:admin_billing_dashboard')
        else:
            form = PaymentForm()
        
        context = {
            'form': form,
            'bill': bill
        }
        return render(request, 'billing/admin/record_payment.html', context)
    except ClinicAdmin.DoesNotExist:
        messages.error(request, 'Admin profile not found')
        return redirect('users:dashboard')

@login_required
def billing_detail(request, billing_id):
    try:
        # Check if user is a doctor
        if hasattr(request.user, 'doctor'):
            doctor = request.user.doctor
            bill = get_object_or_404(Bill, id=billing_id, doctor=doctor)
        # Check if user is a patient
        elif hasattr(request.user, 'patient'):
            patient = request.user.patient
            bill = get_object_or_404(Bill, id=billing_id, patient=patient)
        # Check if user is clinic admin
        elif hasattr(request.user, 'clinicadmin'):
            admin = request.user.clinicadmin
            bill = get_object_or_404(Bill, id=billing_id, clinic=admin.clinic)
        else:
            messages.error(request, 'Unauthorized access')
            return redirect('users:dashboard')

        context = {
            'bill': bill,
            'items': bill.items.all(),
            'payments': bill.payments.all(),
            'user_type': 'doctor' if hasattr(request.user, 'doctor') else 'patient' if hasattr(request.user, 'patient') else 'admin'
        }
        
        return render(request, 'billing/billing_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Error retrieving bill: {str(e)}')
        return redirect('users:dashboard') 