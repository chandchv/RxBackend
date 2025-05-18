from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.urls import reverse

from billing.models import Bill, Payment
from users.models import Patient
from users.decorators import patient_required

@login_required
@patient_required
def billing_history(request):
    """
    View to display billing history for a patient.
    Includes summary stats and paginated list of bills.
    """
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, "Patient profile not found.")
        return redirect('users:dashboard')
    
    # Get all bills for the patient
    bills = Bill.objects.filter(patient=patient).order_by('-bill_date')
    
    # Calculate summary statistics
    total_billed = bills.aggregate(total=Sum('total'))['total'] or 0
    total_paid = bills.filter(status='paid').aggregate(total=Sum('total'))['total'] or 0
    total_paid += bills.filter(status='partial').aggregate(total=Sum('total_paid'))['total_paid'] or 0
    outstanding_balance = total_billed - total_paid
    
    # Bill counts by status
    bill_counts = {
        'total': bills.count(),
        'paid': bills.filter(status='paid').count(),
        'pending': bills.filter(status='pending').count(),
        'partial': bills.filter(status='partial').count(),
    }
    
    # Pagination
    paginator = Paginator(bills, 10)  # 10 bills per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'bills': page_obj.object_list,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'outstanding_balance': outstanding_balance,
        'bill_counts': bill_counts,
    }
    
    return render(request, 'billing/patient/billing_history.html', context)

@login_required
@patient_required
def bill_detail(request, bill_id):
    """
    View to display details of a specific bill for a patient.
    Can be loaded in a modal via HTMX.
    """
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, "Patient profile not found.")
        return redirect('users:dashboard')
    
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    # Check if this is a request to show payment form
    pay_mode = request.GET.get('pay', False)
    
    context = {
        'bill': bill,
        'pay_mode': pay_mode,
    }
    
    return render(request, 'billing/patient/bill_detail.html', context)

@login_required
@patient_required
def process_payment(request, bill_id):
    """
    Process a payment for a bill.
    """
    if request.method != 'POST':
        return redirect('billing:patient_bill_detail', bill_id=bill_id)
    
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, "Patient profile not found.")
        return redirect('users:dashboard')
    
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    if bill.status == 'paid' or bill.status == 'cancelled':
        messages.error(request, "This bill cannot be paid.")
        return redirect('billing:patient_bill_detail', bill_id=bill_id)
    
    try:
        amount = float(request.POST.get('amount', 0))
        payment_method = request.POST.get('payment_method')
        transaction_id = request.POST.get('transaction_id', '')
        notes = request.POST.get('notes', '')
        
        if amount <= 0 or amount > bill.total_pending:
            messages.error(request, f"Invalid payment amount. Maximum allowed: ₹{bill.total_pending}")
            return redirect('billing:patient_bill_detail', bill_id=bill_id)
        
        # Create the payment
        payment = Payment.objects.create(
            bill=bill,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id,
            notes=notes,
            created_by=request.user,
        )
        
        # Update bill status
        if bill.total_paid >= bill.total:
            bill.status = 'paid'
        elif bill.total_paid > 0:
            bill.status = 'partial'
        bill.save()
        
        messages.success(request, f"Payment of ₹{amount} successfully processed.")
        
    except Exception as e:
        messages.error(request, f"Error processing payment: {str(e)}")
    
    return redirect('billing:patient_bill_detail', bill_id=bill_id)

@login_required
@patient_required
def bill_pdf(request, bill_id):
    """
    Generate a PDF for a bill.
    """
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, "Patient profile not found.")
        return redirect('users:dashboard')
    
    bill = get_object_or_404(Bill, id=bill_id, patient=patient)
    
    # This should be implemented to generate the actual PDF
    # For now, return a placeholder response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bill_{bill.bill_number}.pdf"'
    
    # In a real implementation, you would:
    # - Use a PDF library like WeasyPrint, ReportLab, or xhtml2pdf
    # - Render a template to PDF
    # - Write the PDF to the response
    
    # Placeholder text for development
    response.write(b"This is a placeholder for the PDF generation functionality.")
    
    return response 