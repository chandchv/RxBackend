from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from ..models import LabTestPrescription, LabTest, LabTestBooking, Patient
from ..decorators import user_is_doctor
from labs.models import LabProfile
from users.models import Lab

@login_required
@user_is_doctor
def create_lab_prescription(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    
    if request.method == 'POST':
        # Create prescription
        prescription = LabTestPrescription.objects.create(
            doctor=request.user,
            patient=patient,
            notes=request.POST.get('notes', ''),
            preferred_lab_type=request.POST.get('preferred_lab_type', 'PATIENT_CHOICE')
        )
        
        # Add tests
        test_names = request.POST.getlist('test_name[]')
        test_codes = request.POST.getlist('test_code[]')
        test_prices = request.POST.getlist('test_price[]')
        test_instructions = request.POST.getlist('test_instructions[]')
        
        for i in range(len(test_names)):
            LabTest.objects.create(
                prescription=prescription,
                test_name=test_names[i],
                test_code=test_codes[i],
                price=test_prices[i],
                instructions=test_instructions[i]
            )
        
        messages.success(request, 'Lab test prescription created successfully.')
        return redirect('lab_prescription_detail', prescription_id=prescription.id)
    
    # Get nearby labs
    nearby_labs = LabProfile.objects.filter(
        Q(city=patient.city) | Q(state=patient.state)
    ).order_by('name')
    
    # Get in-house labs
    inhouse_labs = Lab.objects.filter(
        clinic=request.user.clinic_admin.clinic
    )
    
    context = {
        'patient': patient,
        'nearby_labs': nearby_labs,
        'inhouse_labs': inhouse_labs
    }
    return render(request, 'doctor/create_lab_prescription.html', context)

@login_required
def lab_prescription_detail(request, prescription_id):
    prescription = get_object_or_404(LabTestPrescription, id=prescription_id)
    
    # Check if user has permission to view
    if not (request.user == prescription.doctor or 
            request.user == prescription.patient.user or
            (hasattr(request.user, 'lab_admin') and 
             request.user.lab_admin.lab == prescription.selected_lab)):
        messages.error(request, 'You do not have permission to view this prescription.')
        return redirect('dashboard')
    
    # Get lab tests for this prescription
    lab_tests = LabTest.objects.filter(prescription=prescription).select_related('test_definition')
    
    context = {
        'prescription': prescription,
        'tests': lab_tests,
        'booking': getattr(prescription, 'booking', None)
    }
    return render(request, 'doctor/lab_prescription_detail.html', context)

@login_required
def book_lab_test(request, prescription_id):
    prescription = get_object_or_404(LabTestPrescription, id=prescription_id)
    
    if request.method == 'POST':
        # Create booking
        booking = LabTestBooking.objects.create(
            prescription=prescription,
            collection_type=request.POST.get('collection_type'),
            collection_address=request.POST.get('collection_address', ''),
            collection_date=timezone.datetime.strptime(
                request.POST.get('collection_date'),
                '%Y-%m-%dT%H:%M'
            ),
            total_amount=sum(test.price for test in prescription.tests.all()),
            commission_amount=sum(test.price for test in prescription.tests.all()) * 
                             (prescription.commission_percentage / 100)
        )
        
        # Update prescription status
        prescription.status = 'BOOKED'
        prescription.save()
        
        messages.success(request, 'Lab test booked successfully.')
        return redirect('lab_prescription_detail', prescription_id=prescription.id)
    
    # Get lab tests for this prescription
    lab_tests = LabTest.objects.filter(prescription=prescription).select_related('test_definition')
    
    context = {
        'prescription': prescription,
        'tests': lab_tests
    }
    return render(request, 'patient/book_lab_test.html', context)

@login_required
def upload_lab_report(request, booking_id):
    booking = get_object_or_404(LabTestBooking, id=booking_id)
    
    if not hasattr(request.user, 'lab_admin') or request.user.lab_admin.lab != booking.prescription.selected_lab:
        messages.error(request, 'You do not have permission to upload reports for this booking.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        report_file = request.FILES.get('report')
        if report_file:
            booking.report = report_file
            booking.report_upload_date = timezone.now()
            booking.report_signed_by = request.user
            booking.status = 'COMPLETED'
            booking.save()
            
            # Update prescription status
            booking.prescription.status = 'COMPLETED'
            booking.prescription.save()
            
            messages.success(request, 'Lab report uploaded successfully.')
            return redirect('lab_prescription_detail', prescription_id=booking.prescription.id)
    
    context = {
        'booking': booking
    }
    return render(request, 'lab/upload_lab_report.html', context) 