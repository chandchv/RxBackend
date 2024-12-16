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
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
import os

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
    try:
        doctor = Doctor.objects.get(user=request.user)
        prescription = get_object_or_404(Prescription, id=pk, doctor=doctor)
        
        context = {
            'prescription': prescription,
            'doctor': doctor
        }
        
        return render(request, 'doctor/prescription_detail.html', context)
        
    except Doctor.DoesNotExist:
        messages.error(request, 'Doctor profile not found')
        return redirect('users:dashboard')
    except Prescription.DoesNotExist:
        messages.error(request, 'Prescription not found')
        return redirect('users:doctor_dashboard')

@login_required
def generate_prescription_pdf(request, pk):
    try:
        doctor = Doctor.objects.get(user=request.user)
        prescription = get_object_or_404(Prescription, id=pk, doctor=doctor)
        
        template = get_template('doctor/prescription_pdf.html')
        context = {
            'prescription': prescription,
            'doctor': doctor
        }
        
        html = template.render(context)
        result = BytesIO()
        
        # Create PDF
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        if not pdf.err:
            # Generate filename
            filename = f"prescription_{prescription.id}_{prescription.patient.last_name}.pdf"
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        return HttpResponse('Error generating PDF', status=400)
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('users:prescription_detail', pk=pk)

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
