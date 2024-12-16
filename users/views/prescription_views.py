from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Prescription, Doctor, Patient
from ..serializers import PrescriptionSerializer
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from ..models import Prescription, PrescriptionItem, Patient, Doctor
from django.utils import timezone

@login_required
def create_prescription(request, patient_id):
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        doctor = get_object_or_404(Doctor, user=request.user)

        if request.method == 'POST':
            # Create the prescription
            prescription = Prescription.objects.create(
                patient=patient,
                doctor=doctor,
                diagnosis=request.POST.get('diagnosis'),
                date=timezone.now(),
                notes=request.POST.get('notes', '')
            )

            # Handle multiple medications
            medicines = request.POST.getlist('medicines[]')
            dosages = request.POST.getlist('dosages[]')
            frequencies = request.POST.getlist('frequencies[]')
            durations = request.POST.getlist('durations[]')
            instructions = request.POST.getlist('instructions[]')

            # Create prescription items
            for i in range(len(medicines)):
                if medicines[i]:  # Only create if medicine name is provided
                    PrescriptionItem.objects.create(
                        prescription=prescription,
                        medicine=medicines[i],
                        dosage=dosages[i],
                        frequency=frequencies[i],
                        duration=durations[i],
                        instructions=instructions[i]
                    )

            messages.success(request, 'Prescription created successfully')
            return redirect('users:prescription_detail', pk=prescription.id)

        return render(request, 'doctor/create_prescription.html', {
            'patient': patient
        })

    except Exception as e:
        print(f"Error creating prescription: {str(e)}")
        messages.error(request, 'Error creating prescription')
        return redirect('users:patient_detail', patient_id=patient_id)

@login_required
def prescription_detail(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    return render(request, 'doctor/prescription_detail.html', {
        'prescription': prescription
    })

@login_required
def patient_prescriptions(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    prescriptions = Prescription.objects.filter(patient=patient).order_by('-date')
    return render(request, 'doctor/patient_prescriptions.html', {
        'patient': patient,
        'prescriptions': prescriptions
    })

@login_required
def prescriptions_view(request):
    prescriptions = Prescription.objects.all().order_by('-date')
    return render(request, 'doctor/prescriptions.html', {
        'prescriptions': prescriptions
    })
