import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.urls import reverse
from django.db import transaction
import datetime
import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

# Set up logging
logger = logging.getLogger(__name__)

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
    paid_count = bills.filter(status='completed').count()
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
    
    # Calculate due amount
    due_amount = bill.total - bill.amount_paid
    
    # Check if we should show payment form
    pay_mode = request.GET.get('pay', False)
    
    # Get related entity based on bill type
    related_entity = None
    if bill.bill_type == 'consultation' and hasattr(bill, 'appointment'):
        related_entity = bill.appointment
    elif bill.bill_type == 'lab' and hasattr(bill, 'lab_order'):
        related_entity = bill.lab_order
    elif bill.bill_type == 'pharmacy' and hasattr(bill, 'pharmacy_order'):
        related_entity = bill.pharmacy_order
    
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'payment_history': payment_history,
        'due_amount': due_amount,
        'pay_mode': pay_mode,
        'related_entity': related_entity,
        'payment_methods': Bill.PAYMENT_METHODS,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'billing/patient/bill_detail_htmx.html', context)
    else:
        return render(request, 'billing/patient/bill_detail.html', context)


@login_required
@user_is_patient
@require_POST
def process_payment(request, bill_id):
    """Process a payment for a bill"""
    patient = request.user.patient
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    # Ensure bill can be paid
    if bill.status == 'completed' or bill.status == 'cancelled':
        messages.error(request, "This bill cannot be paid.")
        return redirect('billing:patient_bill_detail', bill_id=bill.id)
    
    try:
        # Get payment details from form
        payment_amount = float(request.POST.get('payment_amount', 0))
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        # Validate payment amount
        if payment_amount <= 0:
            messages.error(request, "Payment amount must be greater than zero.")
            return redirect('billing:patient_bill_detail', bill_id=bill.id)
        
        due_amount = bill.total - bill.amount_paid
        if payment_amount > due_amount:
            messages.error(request, f"Payment amount cannot exceed the due amount of ₹{due_amount:.2f}.")
            return redirect('billing:patient_bill_detail', bill_id=bill.id)
        
        # Create payment record
        payment = Payment.objects.create(
            bill=bill,
            payment_date=timezone.now(),
            amount=payment_amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            created_by=request.user
        )
        
        # Update bill status and amount paid
        bill.amount_paid += payment_amount
        if bill.amount_paid >= bill.total:
            bill.status = 'completed'
            bill.is_paid = True
        elif bill.amount_paid > 0:
            bill.status = 'partial'
        bill.save()
        
        messages.success(request, f"Payment of ₹{payment_amount:.2f} processed successfully.")
        
    except Exception as e:
        messages.error(request, f"Payment processing failed: {str(e)}")
    
    return redirect('billing:patient_bill_detail', bill_id=bill.id)


def bill_pdf(request, bill_id):
    """Generate PDF for a bill"""
    # Get the bill based on user permissions
    bill = None
    if hasattr(request.user, 'patient'):
        bill = get_object_or_404(Bill, id=bill_id, patient=request.user.patient)
    elif hasattr(request.user, 'doctor'):
        bill = get_object_or_404(Bill, id=bill_id, doctor=request.user.doctor)
    elif request.user.is_staff:
        bill = get_object_or_404(Bill, id=bill_id)
    else:
        return HttpResponse("Unauthorized", status=403)
    
    # For now, return HTML version - you can implement PDF generation later
    bill_items = BillItem.objects.filter(bill=bill)
    payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
    
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'payment_history': payment_history,
    }
    
    return render(request, 'billing/bill_pdf.html', context)


# Doctor Views
@login_required
@user_is_doctor
def doctor_billing_summary(request):
    """Billing summary for a doctor showing key metrics"""
    try:
        doctor = request.user.doctor
        
        # Debug: Print doctor info
        print(f"DEBUG: Doctor ID: {doctor.id}, Name: {doctor.user.get_full_name()}")
        
        # Get date range filters - expand default range to 6 months to catch more bills
        today = timezone.now().date()
        start_date = request.GET.get('start_date', (today - datetime.timedelta(days=180)).isoformat())
        end_date = request.GET.get('end_date', today.isoformat())
        
        # Convert to datetime objects
        try:
            start_date = datetime.date.fromisoformat(start_date)
            end_date = datetime.date.fromisoformat(end_date)
        except ValueError:
            start_date = today - datetime.timedelta(days=180)
            end_date = today
        
        print(f"DEBUG: Date range: {start_date} to {end_date}")
        
        # Check all bills for this doctor (without date filter first)
        all_doctor_bills = Bill.objects.filter(doctor=doctor)
        print(f"DEBUG: Total bills for this doctor: {all_doctor_bills.count()}")
        
        # Check all bills in database
        all_bills = Bill.objects.all()
        print(f"DEBUG: Total bills in database: {all_bills.count()}")
        
        # Get bills for this doctor within date range
        bills = Bill.objects.filter(
            doctor=doctor,
            bill_date__gte=start_date,
            bill_date__lte=end_date
        ).order_by('-bill_date')
        
        print(f"DEBUG: Bills in date range: {bills.count()}")
        
        # If no bills in date range but doctor has bills, expand the range
        if bills.count() == 0 and all_doctor_bills.count() > 0:
            print("DEBUG: No bills in date range, expanding to show all bills for this doctor")
            bills = all_doctor_bills.order_by('-bill_date')
            # Update the date range to match the actual data
            if bills.exists():
                start_date = bills.last().bill_date
                end_date = bills.first().bill_date
                messages.info(request, f"No bills found in selected date range. Showing all {bills.count()} bills for your account.")
        
        # Calculate statistics
        total_bills = bills.count()
        total_amount = bills.aggregate(total=Sum('total'))['total'] or 0
        total_collected = bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
        pending_amount = total_amount - total_collected
        
        # Count by status
        paid_bills = bills.filter(status='completed').count()
        pending_bills = bills.filter(status='pending').count()
        partial_bills = bills.filter(status='partial').count()
        
        # Recent bills for display
        recent_bills = bills[:10]
        
        print(f"DEBUG: Statistics - Total: {total_bills}, Amount: {total_amount}, Collected: {total_collected}")
        
        # Add debug info for template
        debug_info = {
            'doctor_id': doctor.id,
            'doctor_name': doctor.user.get_full_name(),
            'total_bills_all_doctors': all_bills.count(),
            'doctor_has_any_bills': all_doctor_bills.count() > 0,
        }
        
        context = {
            'doctor': doctor,
            'start_date': start_date,
            'end_date': end_date,
            'total_bills': total_bills,
            'total_amount': total_amount,
            'total_collected': total_collected,
            'pending_amount': pending_amount,
            'paid_bills': paid_bills,
            'pending_bills': pending_bills,
            'partial_bills': partial_bills,
            'recent_bills': recent_bills,
            'debug_info': debug_info,
        }
        
        return render(request, 'billing/doctor/billing_summary.html', context)
        
    except Exception as e:
        print(f"DEBUG: Error in billing summary: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error loading billing summary: {str(e)}")
        return redirect('users:doctor_dashboard')


@login_required
@user_is_doctor
def doctor_create_bill(request, appointment_id=None):
    """Create a bill for an appointment or general consultation"""
    doctor = request.user.doctor
    appointment = None
    
    if appointment_id:
        # Get the specific appointment
        from users.models import Appointment
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        # Check if bill already exists
        if hasattr(appointment, 'billing_bill') and appointment.billing_bill:
            messages.info(request, "Bill already exists for this appointment.")
            return redirect('billing:doctor_bill_detail', bill_id=appointment.billing_bill.id)
    
    if request.method == 'POST':
        try:
            patient_id = request.POST.get('patient_id')
            consultation_fee = float(request.POST.get('consultation_fee', 0))
            bill_type = request.POST.get('bill_type', 'consultation')
            notes = request.POST.get('notes', '')
            
            # Get patient
            patient = get_object_or_404(Patient, id=patient_id)
            
            # Create bill
            bill = Bill.objects.create(
                patient=patient,
                doctor=doctor,
                clinic=doctor.clinic,
                appointment=appointment,
                bill_type=bill_type,
                subtotal=consultation_fee,
                total=consultation_fee,
                notes=notes,
                bill_date=timezone.now().date(),
                due_date=timezone.now().date() + datetime.timedelta(days=7)
            )
            
            # Create bill item
            BillItem.objects.create(
                bill=bill,
                item_name=f'Consultation with Dr. {doctor.user.get_full_name()}',
                description=f'Consultation on {timezone.now().date()}',
                quantity=1,
                unit_price=consultation_fee,
                total=consultation_fee
            )
            
            # Create consultation billing record if appointment
            if appointment:
                ConsultationBilling.objects.create(
                    appointment=appointment,
                    bill=bill,
                    doctor=doctor,
                    base_fee=consultation_fee,
                    final_fee=consultation_fee
                )
            
            messages.success(request, f"Bill #{bill.bill_number} created successfully.")
            return redirect('billing:doctor_bill_detail', bill_id=bill.id)
            
        except Exception as e:
            messages.error(request, f"Error creating bill: {str(e)}")
    
    # Get doctor's patients for the form
    patients = Patient.objects.filter(
        Q(appointments__doctor=doctor) |
        Q(billing_bills__doctor=doctor)
    ).distinct()
    
    # Get billing items for the clinic
    billing_items = BillingItem.objects.filter(
        clinic=doctor.clinic,
        is_active=True
    ) if doctor.clinic else BillingItem.objects.none()
    
    context = {
        'doctor': doctor,
        'appointment': appointment,
        'patients': patients,
        'billing_items': billing_items,
    }
    
    return render(request, 'billing/doctor/create_bill.html', context)


@login_required
@user_is_doctor
def doctor_bill_detail(request, bill_id):
    """View for doctors to see bill details"""
    doctor = request.user.doctor
    bill = get_object_or_404(Bill, id=bill_id, doctor=doctor)
    
    bill_items = BillItem.objects.filter(bill=bill)
    payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
    due_amount = bill.total - bill.amount_paid
    
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'payment_history': payment_history,
        'due_amount': due_amount,
    }
    
    return render(request, 'billing/doctor/bill_detail.html', context)


@login_required
@user_is_doctor
def doctor_bills_list(request):
    """List all bills for the doctor with pagination and filtering"""
    doctor = request.user.doctor
    
    # Get all bills for this doctor
    bills = Bill.objects.filter(doctor=doctor).order_by('-bill_date')
    
    # Apply status filter
    status_filter = request.GET.get('status')
    if status_filter:
        bills = bills.filter(status=status_filter)
    
    # Apply date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        try:
            date_from = datetime.date.fromisoformat(date_from)
            bills = bills.filter(bill_date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.date.fromisoformat(date_to)
            bills = bills.filter(bill_date__lte=date_to)
        except ValueError:
            pass
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        bills = bills.filter(
            Q(bill_number__icontains=search_query) |
            Q(patient__user__first_name__icontains=search_query) |
            Q(patient__user__last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(bills, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary stats
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('total'))['total'] or 0
    total_collected = bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
    
    context = {
        'doctor': doctor,
        'bills': page_obj,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'total_collected': total_collected,
        'status_choices': Bill.PAYMENT_STATUS,
        'current_filters': {
            'status': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'search': search_query,
        }
    }
    
    return render(request, 'billing/doctor/bills_list.html', context)


@login_required
@user_is_doctor
def doctor_revenue_dashboard(request):
    """Advanced revenue dashboard with charts and analytics for doctors"""
    try:
        doctor = request.user.doctor
        
        # Get date range filters (default: last 6 months)
        today = timezone.now().date()
        start_date = request.GET.get('start_date', (today - datetime.timedelta(days=180)).isoformat())
        end_date = request.GET.get('end_date', today.isoformat())
        
        # Convert to datetime objects
        try:
            start_date = datetime.date.fromisoformat(start_date)
            end_date = datetime.date.fromisoformat(end_date)
        except ValueError:
            start_date = today - datetime.timedelta(days=180)
            end_date = today
        
        # Get bills for this doctor
        bills = Bill.objects.filter(doctor=doctor)
        
        # Overall statistics
        all_time_bills = bills.count()
        all_time_revenue = bills.aggregate(total=Sum('total'))['total'] or 0
        all_time_collected = bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
        
        # Period statistics
        period_bills = bills.filter(bill_date__gte=start_date, bill_date__lte=end_date)
        period_revenue = period_bills.aggregate(total=Sum('total'))['total'] or 0
        period_collected = period_bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
        period_pending = period_revenue - period_collected
        
        # Monthly revenue data for charts (last 12 months)
        monthly_data = []
        for i in range(12):
            month_start = today.replace(day=1) - datetime.timedelta(days=30*i)
            month_start = month_start.replace(day=1)
            month_end = (month_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
            
            month_bills = bills.filter(bill_date__gte=month_start, bill_date__lte=month_end)
            month_revenue = month_bills.aggregate(total=Sum('total'))['total'] or 0
            month_collected = month_bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'revenue': month_revenue,
                'collected': month_collected,
                'bills_count': month_bills.count()
            })
        
        monthly_data.reverse()  # Oldest first
        
        # Bill type analysis
        bill_type_data = bills.values('bill_type').annotate(
            count=Count('id'),
            revenue=Sum('total')
        ).order_by('-revenue')
        
        # Payment method analysis
        payment_method_data = bills.exclude(payment_method__isnull=True).values('payment_method').annotate(
            count=Count('id'),
            amount=Sum('amount_paid')
        ).order_by('-amount')
        
        # Recent high-value bills
        high_value_bills = period_bills.filter(total__gte=1000).order_by('-total')[:5]
        
        # Patient billing summary
        top_patients = bills.values('patient__first_name', 'patient__last_name', 'patient__id').annotate(
            total_bills=Count('id'),
            total_amount=Sum('total'),
            total_paid=Sum('amount_paid')
        ).order_by('-total_amount')[:10]
        
        # Growth calculation (compare with previous period)
        prev_start = start_date - (end_date - start_date)
        prev_end = start_date - datetime.timedelta(days=1)
        prev_bills = bills.filter(bill_date__gte=prev_start, bill_date__lte=prev_end)
        prev_revenue = prev_bills.aggregate(total=Sum('total'))['total'] or 0
        
        revenue_growth = 0
        if prev_revenue > 0:
            revenue_growth = ((period_revenue - prev_revenue) / prev_revenue) * 100
        
        context = {
            'doctor': doctor,
            'start_date': start_date,
            'end_date': end_date,
            
            # Overall stats
            'all_time_bills': all_time_bills,
            'all_time_revenue': all_time_revenue,
            'all_time_collected': all_time_collected,
            
            # Period stats
            'period_bills': period_bills.count(),
            'period_revenue': period_revenue,
            'period_collected': period_collected,
            'period_pending': period_pending,
            'revenue_growth': revenue_growth,
            
            # Chart data
            'monthly_data': monthly_data,
            'bill_type_data': bill_type_data,
            'payment_method_data': payment_method_data,
            
            # Analysis data
            'high_value_bills': high_value_bills,
            'top_patients': top_patients,
        }
        
        return render(request, 'billing/doctor/revenue_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading revenue dashboard: {str(e)}")
        return redirect('users:doctor_dashboard')


# Admin Views
@login_required
@user_is_admin
def admin_billing_dashboard(request):
    """Billing dashboard for administrators"""
    # Get date range filters
    today = timezone.now().date()
    start_date = request.GET.get('start_date', (today - datetime.timedelta(days=30)).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    
    try:
        start_date = datetime.date.fromisoformat(start_date)
        end_date = datetime.date.fromisoformat(end_date)
    except ValueError:
        start_date = today - datetime.timedelta(days=30)
        end_date = today
    
    # Get all bills within date range
    bills = Bill.objects.filter(
        bill_date__gte=start_date,
        bill_date__lte=end_date
    )
    
    # Calculate overall statistics
    total_bills = bills.count()
    total_billed = bills.aggregate(total=Sum('total'))['total'] or 0
    total_collected = bills.aggregate(collected=Sum('amount_paid'))['collected'] or 0
    total_pending = total_billed - total_collected
    
    # Count by status
    paid_bills = bills.filter(status='completed').count()
    pending_bills = bills.filter(status='pending').count()
    partial_bills = bills.filter(status='partial').count()
    cancelled_bills = bills.filter(status='cancelled').count()
    
    # Overdue bills (past due date and not fully paid)
    overdue_bills = bills.filter(
        due_date__lt=today,
        status__in=['pending', 'partial']
    ).count()
    
    # Top doctors by billing
    top_doctors = bills.values('doctor__user__first_name', 'doctor__user__last_name').annotate(
        total_amount=Sum('total'),
        bill_count=Count('id')
    ).order_by('-total_amount')[:5]
    
    # Recent bills
    recent_bills = bills.order_by('-created_at')[:10]
    
    # Payment methods breakdown
    payment_methods = Payment.objects.filter(
        bill__bill_date__gte=start_date,
        bill__bill_date__lte=end_date
    ).values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_bills': total_bills,
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_pending': total_pending,
        'paid_bills': paid_bills,
        'pending_bills': pending_bills,
        'partial_bills': partial_bills,
        'cancelled_bills': cancelled_bills,
        'overdue_bills': overdue_bills,
        'top_doctors': top_doctors,
        'recent_bills': recent_bills,
        'payment_methods': payment_methods,
    }
    
    return render(request, 'billing/admin/dashboard.html', context)


@login_required
@user_is_admin
def admin_record_payment(request, bill_id):
    """Record a payment for a bill (admin only)"""
    bill = get_object_or_404(Bill, id=bill_id)
    
    if request.method == 'POST':
        try:
            payment_amount = float(request.POST.get('payment_amount', 0))
            payment_method = request.POST.get('payment_method', 'cash')
            reference_number = request.POST.get('reference_number', '')
            notes = request.POST.get('notes', '')
            
            # Validate payment amount
            if payment_amount <= 0:
                messages.error(request, "Payment amount must be greater than zero.")
                return redirect('billing:admin_record_payment', bill_id=bill.id)
            
            due_amount = bill.total - bill.amount_paid
            if payment_amount > due_amount:
                messages.error(request, f"Payment amount cannot exceed the due amount of ₹{due_amount:.2f}.")
                return redirect('billing:admin_record_payment', bill_id=bill.id)
            
            # Create payment record
            payment = Payment.objects.create(
                bill=bill,
                payment_date=timezone.now(),
                amount=payment_amount,
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                created_by=request.user
            )
            
            # Update bill status and amount paid
            bill.amount_paid += payment_amount
            if bill.amount_paid >= bill.total:
                bill.status = 'completed'
                bill.is_paid = True
            elif bill.amount_paid > 0:
                bill.status = 'partial'
            bill.save()
            
            messages.success(request, f"Payment of ₹{payment_amount:.2f} recorded successfully.")
            return redirect('billing:admin_billing_dashboard')
            
        except Exception as e:
            messages.error(request, f"Error recording payment: {str(e)}")
    
    due_amount = bill.total - bill.amount_paid
    payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
    
    context = {
        'bill': bill,
        'due_amount': due_amount,
        'payment_history': payment_history,
        'payment_methods': Bill.PAYMENT_METHODS,
    }
    
    return render(request, 'billing/admin/record_payment.html', context)


@login_required
def staff_record_payment(request, bill_id):
    """Record a payment for a bill (staff and admin access)"""
    try:
        bill = get_object_or_404(Bill, id=bill_id)
        
        # Check permissions - allow staff, doctors, clinic_admin, and superuser
        has_permission = False
        if request.user.is_superuser:
            has_permission = True
        elif hasattr(request.user, 'staff') and request.user.staff.clinic:
            # Staff can record payments for bills in their clinic
            if bill.clinic == request.user.staff.clinic:
                has_permission = True
        elif hasattr(request.user, 'doctor') and request.user.doctor.clinic:
            # Doctors can record payments for their own bills
            if bill.doctor == request.user.doctor:
                has_permission = True
        elif hasattr(request.user, 'clinic_admin') and request.user.clinic_admin.clinic:
            # Clinic admin can record payments for bills in their clinic
            if bill.clinic == request.user.clinic_admin.clinic:
                has_permission = True
        
        if not has_permission:
            messages.error(request, "You don't have permission to record payments for this bill.")
            return redirect('billing:billing_detail', bill_id=bill.id)
        
        if request.method == 'POST':
            try:
                payment_amount = float(request.POST.get('payment_amount', 0))
                payment_method = request.POST.get('payment_method', 'cash')
                reference_number = request.POST.get('reference_number', '')
                notes = request.POST.get('notes', '')
                
                # Validate payment amount
                if payment_amount <= 0:
                    messages.error(request, "Payment amount must be greater than zero.")
                    return redirect('billing:staff_record_payment', bill_id=bill.id)
                
                due_amount = bill.total - bill.amount_paid
                if payment_amount > due_amount:
                    messages.error(request, f"Payment amount cannot exceed the due amount of ₹{due_amount:.2f}.")
                    return redirect('billing:staff_record_payment', bill_id=bill.id)
                
                # Create payment record
                payment = Payment.objects.create(
                    bill=bill,
                    payment_date=timezone.now(),
                    amount=payment_amount,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes,
                    created_by=request.user
                )
                
                # Update bill status and amount paid
                bill.amount_paid += payment_amount
                if bill.amount_paid >= bill.total:
                    bill.status = 'completed'
                    bill.is_paid = True
                elif bill.amount_paid > 0:
                    bill.status = 'partial'
                bill.save()
                
                messages.success(request, f"Payment of ₹{payment_amount:.2f} recorded successfully.")
                return redirect('billing:billing_detail', bill_id=bill.id)
                
            except Exception as e:
                logger.error(f"Error recording payment: {str(e)}", exc_info=True)
                messages.error(request, f"Error recording payment: {str(e)}")
        
        due_amount = bill.total - bill.amount_paid
        payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
        
        context = {
            'bill': bill,
            'due_amount': due_amount,
            'payment_history': payment_history,
            'payment_methods': Bill.PAYMENT_METHODS,
        }
        
        return render(request, 'billing/record_payment.html', context)
        
    except Exception as e:
        logger.error(f"Error in staff_record_payment: {str(e)}", exc_info=True)
        messages.error(request, f"Error accessing payment recording: {str(e)}")
        return redirect('billing:billing_list')


@login_required
@user_is_admin
def admin_bills_list(request):
    """List all bills with filtering and search"""
    bills = Bill.objects.all().order_by('-bill_date')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        bills = bills.filter(status=status_filter)
    
    bill_type_filter = request.GET.get('bill_type')
    if bill_type_filter:
        bills = bills.filter(bill_type=bill_type_filter)
    
    doctor_filter = request.GET.get('doctor')
    if doctor_filter:
        bills = bills.filter(doctor_id=doctor_filter)
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        bills = bills.filter(
            Q(bill_number__icontains=search_query) |
            Q(patient__user__first_name__icontains=search_query) |
            Q(patient__user__last_name__icontains=search_query) |
            Q(doctor__user__first_name__icontains=search_query) |
            Q(doctor__user__last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(bills, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    doctors = Doctor.objects.all()
    
    context = {
        'bills': page_obj,
        'doctors': doctors,
        'status_choices': Bill.PAYMENT_STATUS,
        'bill_type_choices': Bill.BILL_TYPES,
        'current_filters': {
            'status': status_filter,
            'bill_type': bill_type_filter,
            'doctor': doctor_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'billing/admin/bills_list.html', context)


@login_required
def billing_home(request):
    """Home view that redirects to appropriate billing dashboard based on user type"""
    if hasattr(request.user, 'patient'):
        return redirect('billing:patient_billing_history')
    elif hasattr(request.user, 'doctor'):
        return redirect('billing:doctor_billing_summary')
    elif request.user.is_staff or request.user.is_superuser:
        return redirect('billing:admin_billing_dashboard')
    else:
        messages.error(request, "You don't have permission to access billing.")
        return redirect('users:login')


@login_required
@user_is_admin
def admin_edit_bill(request, bill_id):
    """Edit a bill: add extra charges and finalize the bill (admin/staff only)"""
    bill = get_object_or_404(Bill, id=bill_id)
    if bill.status in ['completed', 'finalized', 'cancelled']:
        messages.info(request, "This bill cannot be edited.")
        return redirect('billing:admin_bills_list')

    if request.method == 'POST':
        # Add extra charge
        if 'add_item' in request.POST:
            item_name = request.POST.get('item_name')
            description = request.POST.get('description', '')
            amount = request.POST.get('amount')
            try:
                amount = float(amount)
                if item_name and amount > 0:
                    BillItem.objects.create(
                        bill=bill,
                        item_name=item_name,
                        description=description,
                        quantity=1,
                        unit_price=amount
                    )
                    bill.calculate_total()
                    bill.save()
                    messages.success(request, f"Added extra charge: {item_name} (₹{amount:.2f})")
                else:
                    messages.error(request, "Item name and positive amount required.")
            except Exception as e:
                messages.error(request, f"Error adding item: {str(e)}")
        # Finalize bill
        elif 'finalize_bill' in request.POST:
            bill.status = 'finalized'
            bill.save()
            messages.success(request, "Bill finalized. No further edits allowed.")
            return redirect('billing:admin_bills_list')

    bill_items = BillItem.objects.filter(bill=bill)
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'can_edit': bill.status not in ['completed', 'finalized', 'cancelled'],
    }
    return render(request, 'billing/admin/edit_bill.html', context)


# General Staff/Admin Billing Views
@login_required
def debug_user_access(request):
    """Debug view to check user attributes"""
    debug_info = {
        'user': str(request.user),
        'user_id': request.user.id,
        'is_authenticated': request.user.is_authenticated,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
        'has_staff_attr': hasattr(request.user, 'staff'),
        'has_doctor_attr': hasattr(request.user, 'doctor'),
        'has_clinic_admin_attr': hasattr(request.user, 'clinic_admin'),
        'has_patient_attr': hasattr(request.user, 'patient'),
    }
    
    if hasattr(request.user, 'staff'):
        try:
            debug_info['staff'] = str(request.user.staff)
            debug_info['staff_clinic'] = str(request.user.staff.clinic) if request.user.staff.clinic else None
        except Exception as e:
            debug_info['staff_error'] = str(e)
    
    if hasattr(request.user, 'doctor'):
        try:
            debug_info['doctor'] = str(request.user.doctor)
            debug_info['doctor_clinic'] = str(request.user.doctor.clinic) if request.user.doctor.clinic else None
        except Exception as e:
            debug_info['doctor_error'] = str(e)
    
    return JsonResponse(debug_info, indent=2)


@login_required 
def create_bill(request):
    """Create a new bill with comprehensive error handling"""
    try:
        logger.info(f"Create bill accessed by user: {request.user.id} ({request.user.username})")
        
        # Check user permissions - be more inclusive and debug
        clinic = None
        user_type = None
        
        # Debug what user attributes exist
        user_attrs = {
            'has_staff': hasattr(request.user, 'staff'),
            'has_doctor': hasattr(request.user, 'doctor'), 
            'has_clinic_admin': hasattr(request.user, 'clinic_admin'),
            'is_superuser': request.user.is_superuser,
            'is_staff': request.user.is_staff,
        }
        
        if hasattr(request.user, 'staff'):
            try:
                staff = request.user.staff
                if staff and staff.clinic:
                    clinic = staff.clinic
                    user_type = 'staff'
            except:
                pass
        
        if not clinic and hasattr(request.user, 'doctor'):
            try:
                doctor = request.user.doctor
                if doctor and doctor.clinic:
                    clinic = doctor.clinic
                    user_type = 'doctor'
            except:
                pass
        
        if not clinic and hasattr(request.user, 'clinic_admin'):
            try:
                clinic_admin = request.user.clinic_admin
                if clinic_admin and clinic_admin.clinic:
                    clinic = clinic_admin.clinic
                    user_type = 'clinic_admin'
            except:
                pass
        
        if not clinic and (request.user.is_superuser or request.user.is_staff):
            # For superuser/staff, get first available clinic or let them select
            from users.models import Clinic
            clinic = Clinic.objects.first()
            user_type = 'superuser' if request.user.is_superuser else 'staff_user'
        
        if not clinic:
            # Debug message with user attributes
            debug_msg = f'No clinic access found. User attributes: {user_attrs}. Please contact your administrator.'
            logger.error(debug_msg)
            messages.error(request, debug_msg)
            return redirect('users:dashboard')
        
        # Get completed appointments that don't have bills yet
        from users.models import Appointment
        completed_appointments = Appointment.objects.filter(
            doctor__clinic=clinic,
            status='completed'
        ).select_related('patient', 'doctor').order_by('-appointment_date')
        
        # Note: We'll show all completed appointments and let the user choose
        # This avoids the UUID type mismatch issue completely
        # The form will still work properly even if some appointments already have bills
        
        # Get patients for creating bills without appointments
        from users.models import Patient, Doctor
        patients = Patient.objects.filter(clinic=clinic).order_by('first_name')
        doctors = Doctor.objects.filter(clinic=clinic).order_by('name')
        
        if request.method == 'POST':
            try:
                logger.info("Processing bill creation form submission")
                
                # Get form data
                patient_id = request.POST.get('patient')
                doctor_id = request.POST.get('doctor')
                appointment_id = request.POST.get('appointment')
                bill_type = request.POST.get('bill_type', 'consultation')
                notes = request.POST.get('notes', '')
                
                # Get bill items data
                item_names = request.POST.getlist('item_name[]')
                item_descriptions = request.POST.getlist('item_description[]')
                item_quantities = request.POST.getlist('item_quantity[]')
                item_prices = request.POST.getlist('item_price[]')
                
                logger.debug(f"Form data: patient_id={patient_id}, doctor_id={doctor_id}, appointment_id={appointment_id}")
                logger.debug(f"Items: {len(item_names)} items")
                
                # Validate required fields
                if not patient_id:
                    logger.warning("No patient selected in form")
                    messages.error(request, 'Please select a patient.')
                    return redirect('billing:create_bill')
                
                if not item_names or not any(item_names):
                    logger.warning("No bill items provided")
                    messages.error(request, 'Please add at least one bill item.')
                    return redirect('billing:create_bill')
                
                # Get patient and doctor with error handling
                try:
                    patient = get_object_or_404(Patient, id=patient_id, clinic=clinic)
                    logger.debug(f"Found patient: {patient.get_full_name()}")
                except Exception as e:
                    logger.error(f"Error getting patient {patient_id}: {str(e)}")
                    messages.error(request, f'Invalid patient selected: {str(e)}')
                    return redirect('billing:create_bill')
                
                doctor = None
                if doctor_id:
                    try:
                        doctor = get_object_or_404(Doctor, id=doctor_id, clinic=clinic)
                        logger.debug(f"Found doctor: {doctor.name}")
                    except Exception as e:
                        logger.error(f"Error getting doctor {doctor_id}: {str(e)}")
                        messages.error(request, f'Invalid doctor selected: {str(e)}')
                        return redirect('billing:create_bill')
                
                # Get appointment if specified - handle UUID carefully
                appointment = None
                if appointment_id:
                    try:
                        # First check if appointment_id looks like a valid UUID
                        import uuid
                        try:
                            uuid.UUID(str(appointment_id))
                        except ValueError:
                            logger.error(f"Invalid UUID format for appointment: {appointment_id}")
                            messages.error(request, 'Invalid appointment ID format.')
                            return redirect('billing:create_bill')
                        
                        appointment = get_object_or_404(Appointment, id=appointment_id, doctor__clinic=clinic)
                        doctor = appointment.doctor  # Use appointment's doctor
                        logger.debug(f"Found appointment: {appointment.id} for {appointment.patient.get_full_name()}")
                        
                        # Check if this appointment already has a bill - safely
                        try:
                            if hasattr(appointment, 'billing_bill') and appointment.billing_bill:
                                logger.warning(f"Appointment {appointment_id} already has a bill: {appointment.billing_bill.bill_number}")
                                messages.warning(request, f'This appointment already has a bill: {appointment.billing_bill.bill_number}')
                                return redirect('billing:billing_detail', bill_id=appointment.billing_bill.id)
                        except Exception as bill_check_error:
                            # If checking for existing bill fails, continue anyway
                            logger.warning(f"Could not check for existing bill: {str(bill_check_error)}")
                        
                    except Exception as e:
                        logger.error(f"Error getting appointment {appointment_id}: {str(e)}")
                        messages.error(request, f'Invalid appointment selected: {str(e)}')
                        return redirect('billing:create_bill')
                
                # Use database transaction to ensure data integrity
                with transaction.atomic():
                    logger.info("Creating bill...")
                    
                    # Create the bill - handle UUID appointment carefully
                    bill_data = {
                        'patient': patient,
                        'doctor': doctor,
                        'clinic': clinic,
                        'bill_type': bill_type,
                        'bill_date': timezone.now().date(),
                        'due_date': timezone.now().date() + datetime.timedelta(days=30),
                        'status': 'pending',
                        'notes': notes
                    }
                    
                    # Only add appointment if it exists - this avoids UUID issues
                    if appointment:
                        bill_data['appointment'] = appointment
                    
                    try:
                        bill = Bill.objects.create(**bill_data)
                        logger.info(f"Bill created successfully: {bill.bill_number}")
                    except Exception as bill_create_error:
                        logger.error(f"Error creating bill: {str(bill_create_error)}", exc_info=True)
                        if "uuid" in str(bill_create_error).lower() and "bigint" in str(bill_create_error).lower():
                            messages.error(request, 'Database configuration error: UUID/BigInt mismatch. Please contact administrator.')
                        else:
                            messages.error(request, f'Error creating bill: {str(bill_create_error)}')
                        return redirect('billing:create_bill')
                    
                    # Create bill items AFTER the bill is saved (so it has a primary key)
                    from decimal import Decimal
                    items_created = 0
                    for i, item_name in enumerate(item_names):
                        if item_name and i < len(item_quantities) and i < len(item_prices):
                            try:
                                quantity = int(item_quantities[i]) if item_quantities[i] else 1
                                price = Decimal(item_prices[i]) if item_prices[i] else Decimal('0.00')
                                description = item_descriptions[i] if i < len(item_descriptions) else ''
                                
                                # Create bill item - the save method automatically calculates totals
                                bill_item = BillItem.objects.create(
                                    bill=bill,
                                    item_name=item_name,
                                    description=description,
                                    quantity=quantity,
                                    unit_price=price
                                )
                                items_created += 1
                                logger.debug(f"Created bill item: {item_name}, qty: {quantity}, price: {price}")
                            except (ValueError, IndexError) as e:
                                logger.error(f"Error creating bill item {i}: {str(e)}")
                                continue
                            except Exception as e:
                                logger.error(f"Unexpected error creating bill item {i}: {str(e)}")
                                continue
                    
                    logger.info(f"Created {items_created} bill items")
                    
                    # The BillItem save method already called bill.calculate_total() and bill.save()
                    # So we just need to refresh the bill object
                    bill.refresh_from_db()
                    
                    # If this is for a completed appointment, create consultation billing
                    if appointment and bill_type == 'consultation':
                        try:
                            # Check if consultation billing already exists
                            existing_cb = ConsultationBilling.objects.filter(appointment=appointment).first()
                            if not existing_cb:
                                ConsultationBilling.objects.create(
                                    appointment=appointment,
                                    bill=bill,
                                    doctor=doctor,
                                    base_fee=bill.total,
                                    final_fee=bill.total
                                )
                                logger.info(f"ConsultationBilling created for appointment: {appointment.id}")
                            else:
                                logger.warning(f"ConsultationBilling already exists for appointment: {appointment.id}")
                        except Exception as cb_error:
                            logger.error(f"Error creating ConsultationBilling: {str(cb_error)}", exc_info=True)
                            # Don't fail the whole bill creation for this
                    
                    logger.info(f"Bill creation completed successfully: {bill.bill_number}")
                    messages.success(request, f'Bill #{bill.bill_number} created successfully!')
                    return redirect('billing:billing_detail', bill_id=bill.id)
                
            except Exception as e:
                logger.error(f'Unexpected error creating bill: {str(e)}', exc_info=True)
                # Check for specific database errors
                if "uuid" in str(e).lower() and "bigint" in str(e).lower():
                    messages.error(request, 'Database configuration error: There is a type mismatch between UUID and BigInt fields. Please contact your system administrator.')
                elif "duplicate key" in str(e).lower():
                    messages.error(request, 'A bill for this appointment already exists.')
                else:
                    messages.error(request, f'Error creating bill: {str(e)}')
        
        context = {
            'user_type': user_type,
            'clinic': clinic,
            'completed_appointments': completed_appointments,
            'patients': patients,
            'doctors': doctors,
        }
        
        return render(request, 'billing/create_bill.html', context)
        
    except Exception as e:
        logger.error(f'Unexpected error in create_bill: {str(e)}', exc_info=True)
        messages.error(request, f'Error accessing create bill page: {str(e)}')
        return redirect('users:dashboard')


@login_required
def billing_list(request):
    """General billing list view for staff/admin/doctors"""
    # Check user permissions and get clinic - be more inclusive
    clinic = None
    bills = Bill.objects.none()  # Empty queryset by default
    
    if hasattr(request.user, 'staff'):
        try:
            staff = request.user.staff
            if staff and staff.clinic:
                clinic = staff.clinic
                bills = Bill.objects.filter(clinic=clinic)
        except:
            pass
    
    if not bills.exists() and hasattr(request.user, 'doctor'):
        try:
            doctor = request.user.doctor
            if doctor and doctor.clinic:
                clinic = doctor.clinic
                bills = Bill.objects.filter(doctor=doctor)
        except:
            pass
    
    if not bills.exists() and hasattr(request.user, 'clinic_admin'):
        try:
            clinic_admin = request.user.clinic_admin
            if clinic_admin and clinic_admin.clinic:
                clinic = clinic_admin.clinic
                bills = Bill.objects.filter(clinic=clinic)
        except:
            pass
    
    if not bills.exists() and (request.user.is_superuser or request.user.is_staff):
        bills = Bill.objects.all()
    
    if not bills.exists():
        messages.error(request, 'No billing access found. Please contact your administrator.')
        return redirect('users:dashboard')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        bills = bills.filter(status=status_filter)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        bills = bills.filter(
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(doctor__name__icontains=search_query) |
            Q(bill_number__icontains=search_query)
        )
    
    bills = bills.select_related('patient', 'doctor').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(bills, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bills': page_obj,
        'clinic': clinic,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': Bill.PAYMENT_STATUS,
    }
    
    return render(request, 'billing/billing_list.html', context)


@login_required
def billing_detail(request, bill_id):
    """General billing detail view for staff/admin/doctors"""
    # Check user permissions and get the bill
    bill = None
    
    if hasattr(request.user, 'staff') and request.user.staff.clinic:
        bill = get_object_or_404(Bill, id=bill_id, clinic=request.user.staff.clinic)
    elif hasattr(request.user, 'doctor') and request.user.doctor.clinic:
        bill = get_object_or_404(Bill, id=bill_id, doctor=request.user.doctor)
    elif hasattr(request.user, 'clinic_admin') and request.user.clinic_admin.clinic:
        bill = get_object_or_404(Bill, id=bill_id, clinic=request.user.clinic_admin.clinic)
    elif hasattr(request.user, 'patient') and request.user.patient:
        bill = get_object_or_404(Bill, id=bill_id, patient=request.user.patient)
    elif request.user.is_superuser:
        bill = get_object_or_404(Bill, id=bill_id)
    else:
        messages.error(request, 'No billing access found. Please contact your administrator.')
        return redirect('users:dashboard')
    
    # Get bill items and payment history
    bill_items = BillItem.objects.filter(bill=bill)
    payment_history = Payment.objects.filter(bill=bill).order_by('-payment_date')
    
    # Calculate due amount
    due_amount = bill.total - bill.amount_paid
    
    # Get related entity based on bill type
    related_entity = None
    if bill.bill_type == 'consultation' and hasattr(bill, 'appointment') and bill.appointment:
        related_entity = bill.appointment
    
    context = {
        'bill': bill,
        'bill_items': bill_items,
        'payment_history': payment_history,
        'due_amount': due_amount,
        'related_entity': related_entity,
        'can_edit': bill.status not in ['completed', 'cancelled'] and (
            hasattr(request.user, 'staff') or 
            hasattr(request.user, 'clinic_admin') or 
            request.user.is_superuser
        )
    }
    
    return render(request, 'billing/billing_detail.html', context)


@login_required
def bill_print(request, bill_id):
    """Generate printable bill"""
    try:
        bill = get_object_or_404(Bill, id=bill_id)
        
        # Check permissions - allow access to bill based on user type
        has_permission = False
        if request.user.is_superuser:
            has_permission = True
        elif hasattr(request.user, 'staff') and request.user.staff.clinic:
            if bill.clinic == request.user.staff.clinic:
                has_permission = True
        elif hasattr(request.user, 'doctor') and request.user.doctor:
            if bill.doctor == request.user.doctor:
                has_permission = True
        elif hasattr(request.user, 'clinic_admin') and request.user.clinic_admin.clinic:
            if bill.clinic == request.user.clinic_admin.clinic:
                has_permission = True
        elif hasattr(request.user, 'patient') and request.user.patient:
            if bill.patient == request.user.patient:
                has_permission = True
        
        if not has_permission:
            messages.error(request, "You don't have permission to access this bill.")
            return redirect('billing:billing_list')
        
        bill_items = BillItem.objects.filter(bill=bill)
        payments = Payment.objects.filter(bill=bill).order_by('-payment_date')
        
        context = {
            'bill': bill,
            'bill_items': bill_items,
            'payments': payments,
            'clinic': bill.clinic,
            'patient': bill.patient,
            'doctor': bill.doctor,
            'print_date': timezone.now(),
        }
        
        return render(request, 'billing/bill_print.html', context)
        
    except Exception as e:
        logger.error(f"Error in bill_print: {str(e)}", exc_info=True)
        messages.error(request, f"Error generating printable bill: {str(e)}")
        return redirect('billing:billing_list') 