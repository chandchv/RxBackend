from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import Billing, Appointment, Patient

@login_required
def create_billing(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        patient = appointment.patient

        # Check if the patient is eligible for a free appointment
        if Billing.get_free_appointment_eligibility(patient):
            amount = 0.00
            is_paid = False
        else:
            amount = 100.00  # Example amount
            is_paid = True

        billing = Billing.objects.create(
            patient=patient,
            appointment=appointment,
            amount=amount,
            is_paid=is_paid
        )

        messages.success(request, 'Billing created successfully.')
        return redirect('users:billing_detail', billing_id=billing.id)

    except Appointment.DoesNotExist:
        messages.error(request, 'Appointment not found.')
        return redirect('users:dashboard') 

@login_required
def billing_detail(request, billing_id):
    billing = get_object_or_404(Billing, id=billing_id)
    context = {
        'billing': billing
    }
    return render(request, 'billing/billing_detail.html', context) 