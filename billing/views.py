from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.urls import reverse
import datetime
import json
from django.views.decorators.http import require_POST

from .models import (
    Bill, BillItem, Payment, BillingItem, 
    LabTestBilling, ConsultationBilling, InsuranceClaim
)
from .forms import (
    BillForm, BillItemForm, PaymentForm, 
    InsuranceClaimForm, LabTestBillingForm
)
from users.models import Patient, Doctor, Clinic
from users.decorators import user_is_admin, user_is_doctor, user_is_staff, user_is_patient


# Patient Views
@login_required
@user_is_patient
def patient_billing_history(request):
    """View for patients to see their billing history with summary statistics"""
    patient = request.user.patient
    
    # Get all bills for the patient
    bills = Bill.objects.filter(patient=patient).order_by('-bill_date')
    
    # Calculate summary statistics
    total_billed = bills.aggregate(total=Sum('total'))['total'] or 0
    total_paid = bills.aggregate(paid=Sum('amount_paid'))['paid'] or 0
    outstanding_balance = total_billed - total_paid
    
    # Count bills by status
    paid_count = bills.filter(status='paid').count()
    pending_count = bills.filter(status='pending').count()
    partial_count = bills.filter(status='partial').count()
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        bills = bills.filter(
            Q(bill_number__icontains=search_query) |
            Q(bill_type__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(bills, 10)  # Show 10 bills per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bills': page_obj,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'outstanding_balance': outstanding_balance,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'partial_count': partial_count,
        'search_query': search_query,
    }
    
    return render(request, 'billing/patient/billing_history.html', context)


@login_required
@user_is_patient
def patient_bill_detail(request, bill_id):
    """View for patients to see details of a specific bill and make payments"""
    patient = request.user.patient
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    # Get bill items
    bill_items = BillItem.objects.filter(bill=bill)
    
    # Get payment history
    payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
    
    # Check if we should show payment form
    pay_mode = request.GET.get('pay', False)
    
    # Get related entity based on bill type
    related_entity = None
    if bill.bill_type == 'appointment' and hasattr(bill, 'appointment'):
        related_entity = bill.appointment
    elif bill.bill_type == 'lab' and hasattr(bill, 'lab_order'):
        related_entity = bill.lab_order
    elif bill.bill_type == 'pharmacy' and hasattr(bill, 'pharmacy_order'):
        related_entity = bill.pharmacy_order
    
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'payment_history': payment_history,
        'pay_mode': pay_mode,
        'related_entity': related_entity,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'billing/patient/bill_detail.html', context)
    else:
        return render(request, 'billing/patient/view_bill.html', context)


@login_required
@user_is_patient
@require_POST
def process_payment(request, bill_id):
    """Process a payment for a bill"""
    patient = request.user.patient
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    # Ensure bill can be paid
    if bill.status == 'paid' or bill.status == 'cancelled':
        messages.error(request, "This bill cannot be paid.")
        return redirect('billing:patient_bill_detail', bill_id=bill.id)
    
    try:
        # Get payment details from form
        payment_amount = float(request.POST.get('payment_amount', 0))
        payment_method = request.POST.get('payment_method')
        reference_number = request.POST.get('reference_number', '')
        
        # Validate payment amount
        if payment_amount <= 0:
            messages.error(request, "Payment amount must be greater than zero.")
            return redirect('billing:patient_bill_detail', bill_id=bill.id)
        
        if payment_amount > bill.due_amount:
            messages.error(request, "Payment amount cannot exceed the due amount.")
            return redirect('billing:patient_bill_detail', bill_id=bill.id)
        
        # Create payment record
        payment = Payment.objects.create(
            bill=bill,
            payment_date=timezone.now(),
            amount=payment_amount,
            payment_method=payment_method,
            reference_number=reference_number,
            created_by=request.user
        )
        
        # Update bill status and amount paid
        bill.amount_paid += payment_amount
        if bill.amount_paid >= bill.total:
            bill.status = 'paid'
        elif bill.amount_paid > 0:
            bill.status = 'partial'
        bill.save()
        
        messages.success(request, f"Payment of ₹{payment_amount:.2f} processed successfully.")
        
    except Exception as e:
        messages.error(request, f"Payment processing failed: {str(e)}")
    
    return redirect('billing:patient_bill_detail', bill_id=bill.id)


def bill_pdf(request, bill_id):
    """Generate PDF for a bill"""
    # Placeholder for PDF generation functionality
    # You would need to implement this using a library like ReportLab, WeasyPrint, etc.
    # For now, just return a simple HTTP response
    return HttpResponse("PDF generation will be implemented here.", content_type="text/plain")


# Doctor Views
@login_required
@user_is_doctor
def doctor_billing_summary(request):
    """Billing summary for a doctor showing key metrics"""
    try:
        doctor = request.user.doctor
        
        # Get date range filters
        today = timezone.now().date()
        start_date = request.GET.get('start_date', (today - datetime.timedelta(days=30)).isoformat())
        end_date = request.GET.get('end_date', today.isoformat())
        
        # Convert to datetime objects
        try:
            start_date = datetime.date.fromisoformat(start_date)
            end_date = datetime.date.fromisoformat(end_date)
        except ValueError:
            start_date = today - datetime.timedelta(days=30)
            end_date = today
        
        # Get bills for this doctor within date range
        bills = Bill.objects.filter(
            doctor=doctor,
            bill_date__gte=start_date,
            bill_date__lte=end_date
        ).order_by('-bill_date')
        
        # Calculate statistics
        total_bills = bills.count()
        total_amount = bills.aggregate(Sum('total'))['total__sum'] or 0
        paid_amount = bills.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        pending_amount = total_amount - paid_amount
        
        # Consultation vs. Lab Test breakdown
        consultation_bills = bills.filter(bill_type='consultation')
        lab_bills = bills.filter(bill_type='lab_test')
        consultation_amount = consultation_bills.aggregate(Sum('total'))['total__sum'] or 0
        lab_amount = lab_bills.aggregate(Sum('total'))['total__sum'] or 0
        
        # Recent bills
        recent_bills = bills[:10]
        
        context = {
            'doctor': doctor,
            'start_date': start_date,
            'end_date': end_date,
            'total_bills': total_bills,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'pending_amount': pending_amount,
            'consultation_amount': consultation_amount,
            'lab_amount': lab_amount,
            'recent_bills': recent_bills
        }
        return render(request, 'billing/doctor/billing_summary.html', context)
    except Exception as e:
        messages.error(request, f'Error retrieving billing summary: {str(e)}')
        return redirect('dashboard')


@login_required
@user_is_doctor
def doctor_create_bill(request, appointment_id=None):
    """Create a new bill for a doctor's appointment"""
    try:
        doctor = request.user.doctor
        
        # If appointment ID is provided, get the appointment
        appointment = None
        patient = None
        
        if appointment_id:
            appointment = get_object_or_404(
                'users.Appointment', 
                id=appointment_id, 
                doctor=doctor, 
                status='completed'
            )
            patient = appointment.patient
        
        if request.method == 'POST':
            form = BillForm(request.POST)
            if form.is_valid():
                bill = form.save(commit=False)
                bill.doctor = doctor
                bill.clinic = doctor.clinic
                
                # If no appointment is linked, verify patient access
                if not appointment:
                    patient_id = form.cleaned_data.get('patient')
                    patient = get_object_or_404(Patient, id=patient_id)
                    
                bill.patient = patient
                bill.bill_type = 'consultation'
                bill.save()
                
                # Add bill items from the form
                item_data = json.loads(request.POST.get('bill_items', '[]'))
                for item in item_data:
                    BillItem.objects.create(
                        bill=bill,
                        item_name=item['name'],
                        description=item['description'],
                        quantity=item['quantity'],
                        unit_price=item['price']
                    )
                
                # Recalculate totals
                bill.calculate_total()
                bill.save()
                
                messages.success(request, 'Bill created successfully!')
                return redirect('billing:doctor_billing_summary')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            # Pre-populate form with appointment data if available
            initial_data = {}
            if appointment:
                initial_data = {
                    'patient': patient.id,
                    'bill_date': appointment.appointment_date,
                    'notes': f"Consultation with Dr. {doctor.name} on {appointment.appointment_date}"
                }
            form = BillForm(initial=initial_data)
        
        # Get billing items for this clinic
        billing_items = BillingItem.objects.filter(
            clinic=doctor.clinic, 
            is_active=True
        ).order_by('item_type', 'name')
        
        context = {
            'form': form,
            'doctor': doctor,
            'appointment': appointment,
            'patient': patient,
            'billing_items': billing_items
        }
        return render(request, 'billing/doctor/create_bill.html', context)
    except Exception as e:
        messages.error(request, f'Error creating bill: {str(e)}')
        return redirect('dashboard')


# Admin Views
@login_required
@user_is_admin
def admin_billing_dashboard(request):
    """Admin dashboard showing all billing information"""
    try:
        # Get clinic (either from admin user or selected via session)
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            if not clinic_id:
                # Default to first clinic if none selected
                clinic = Clinic.objects.first()
                if clinic:
                    clinic_id = clinic.id
                    request.session['current_clinic_id'] = clinic_id
            else:
                clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            # Get clinic from user profile
            clinic = request.user.clinic_admin.clinic if hasattr(request.user, 'clinic_admin') else None
        
        if not clinic:
            messages.error(request, 'No clinic found. Please set up a clinic first.')
            return redirect('dashboard')
        
        # Date range filters
        today = timezone.now().date()
        start_date = request.GET.get('start_date', (today - datetime.timedelta(days=30)).isoformat())
        end_date = request.GET.get('end_date', today.isoformat())
        
        # Convert to datetime objects
        try:
            start_date = datetime.date.fromisoformat(start_date)
            end_date = datetime.date.fromisoformat(end_date)
        except ValueError:
            start_date = today - datetime.timedelta(days=30)
            end_date = today
        
        # Get bills for this clinic within date range
        bills = Bill.objects.filter(
            clinic=clinic,
            bill_date__gte=start_date,
            bill_date__lte=end_date
        ).order_by('-bill_date')
        
        # Calculate statistics
        total_bills = bills.count()
        total_revenue = bills.aggregate(Sum('total'))['total__sum'] or 0
        collected_revenue = Payment.objects.filter(
            bill__clinic=clinic,
            payment_date__gte=start_date,
            payment_date__lte=end_date
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        pending_revenue = total_revenue - collected_revenue
        
        # Bill type breakdown
        bill_types = bills.values('bill_type').annotate(
            count=Count('id'),
            total=Sum('total')
        ).order_by('-total')
        
        # Doctor breakdown
        doctor_breakdown = bills.values(
            'doctor__id', 'doctor__name'
        ).annotate(
            count=Count('id'),
            total=Sum('total')
        ).order_by('-total')
        
        # Recent bills
        recent_bills = bills[:10]
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            bill__clinic=clinic
        ).order_by('-payment_date')[:10]
        
        context = {
            'clinic': clinic,
            'start_date': start_date,
            'end_date': end_date,
            'total_bills': total_bills,
            'total_revenue': total_revenue,
            'collected_revenue': collected_revenue,
            'pending_revenue': pending_revenue,
            'bill_types': bill_types,
            'doctor_breakdown': doctor_breakdown,
            'recent_bills': recent_bills,
            'recent_payments': recent_payments
        }
        return render(request, 'billing/admin/billing_dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error retrieving billing dashboard: {str(e)}')
        return redirect('dashboard')


@login_required
@user_is_admin
def admin_record_payment(request, bill_id):
    """Record a payment against a bill"""
    try:
        # Get clinic (either from admin user or selected via session)
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            clinic = get_object_or_404(Clinic, id=clinic_id) if clinic_id else Clinic.objects.first()
        else:
            clinic = request.user.clinic_admin.clinic
        
        bill = get_object_or_404(Bill, id=bill_id, clinic=clinic)
        
        if request.method == 'POST':
            form = PaymentForm(request.POST)
            if form.is_valid():
                payment = form.save(commit=False)
                payment.bill = bill
                payment.recorded_by = request.user
                payment.save()
                
                # Update bill status
                bill.update_status()
                bill.save()
                
                messages.success(request, 'Payment recorded successfully!')
                return redirect('billing:admin_billing_dashboard')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            # Calculate amount due
            total_paid = bill.payments.aggregate(Sum('amount'))['amount__sum'] or 0
            amount_due = bill.total - total_paid
            
            form = PaymentForm(initial={
                'amount': amount_due,
                'payment_date': timezone.now().date()
            })
        
        context = {
            'form': form,
            'bill': bill,
            'clinic': clinic
        }
        return render(request, 'billing/admin/record_payment.html', context)
    except Exception as e:
        messages.error(request, f'Error recording payment: {str(e)}')
        return redirect('billing:admin_billing_dashboard')


@login_required
def billing_home(request):
    """Home page for the billing module that redirects based on user role"""
    if hasattr(request.user, 'patient'):
        return redirect('billing:patient_billing_history')
    elif hasattr(request.user, 'doctor'):
        return redirect('billing:doctor_billing_summary')
    elif request.user.is_staff:
        return redirect('billing:admin_billing_dashboard')
    else:
        messages.warning(request, "You don't have access to the billing module.")
        return redirect('dashboard') 