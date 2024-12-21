from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Prescription, Doctor, Patient, PrescriptionItem, PatientVitals
from ..serializers import PrescriptionSerializer
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from ..models import Prescription, PrescriptionItem, Patient, Doctor
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
import os
import json


@login_required
def create_prescription(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    doctor = get_object_or_404(Doctor, user=request.user)
    
    if request.method == 'POST':
        try:
            # Debug print statements
            print("POST data:", request.POST)
            
            # Convert empty strings to None for decimal fields
            weight = request.POST.get('weight', '')
            print(f"Raw weight: {weight}")
            weight = float(weight) if weight.strip() else None
            
            height = request.POST.get('height', '')
            print(f"Raw height: {height}")
            height = float(height) if height.strip() else None
            
            blood_pressure = request.POST.get('blood_pressure', '').strip()
            print(f"Raw BP: {blood_pressure}")
            blood_pressure = blood_pressure if blood_pressure else None

            temperature = request.POST.get('temperature', '')
            temperature = float(temperature) if temperature.strip() else None

            heart_rate = request.POST.get('heart_rate', '')
            heart_rate = float(heart_rate) if heart_rate.strip() else None

            oxygen_saturation = request.POST.get('oxygen_saturation', '')
            oxygen_saturation = float(oxygen_saturation) if oxygen_saturation.strip() else None

            print(f"Processed values - Weight: {weight}, Height: {height}, BP: {blood_pressure}, Temperature: {temperature}, Heart Rate: {heart_rate}, Oxygen Saturation: {oxygen_saturation}")

            # Save vitals first
            vitals = PatientVitals.objects.create(
                patient=patient,
                weight=weight,
                height=height,
                blood_pressure=blood_pressure,
                temperature=temperature,
                heart_rate=heart_rate,
                oxygen_saturation=oxygen_saturation,
                recorded_by=request.user
            )
            print(f"Created vitals: {vitals.id}")

            # Create prescription
            prescription = Prescription.objects.create(
                patient=patient,
                doctor=doctor,
                chief_complaints=request.POST.get('chief_complaints'),
                clinical_findings=request.POST.get('clinical_findings'),
                date=timezone.now(),
                diagnosis=request.POST.get('diagnosis'),
                advice=request.POST.get('advice', ''),
                follow_up_date=request.POST.get('follow_up_date') or None
            )

            # Handle medicines
            medicines_data = json.loads(request.POST.get('prescription_medicines', '[]'))
            for medicine in medicines_data:
                PrescriptionItem.objects.create(
                    prescription=prescription,
                    medicine=medicine['name'],
                    dosage=medicine['dosage'],
                    duration=medicine['duration'],
                    duration_unit=medicine['duration_unit'],
                    instructions=medicine['instructions']
                )

            messages.success(request, 'Prescription created successfully')
            return redirect('users:prescription_detail', pk=prescription.id)

        except ValueError as e:
            print(f"ValueError in create_prescription: {e}")
            messages.error(request, f'Invalid value entered for vitals: {str(e)}')
            return redirect('users:create_prescription', patient_id=patient_id)
        except Exception as e:
            print(f"Exception in create_prescription: {e}")
            messages.error(request, f'Error creating prescription: {str(e)}')
            return redirect('users:patient_detail', patient_id=patient_id)

    # Get latest vitals for pre-filling the form
    latest_vitals = PatientVitals.objects.filter(patient=patient).order_by('-recorded_at').first()

    context = {
        'patient': patient,
        'doctor': doctor,
        'vitals': latest_vitals
    }
    return render(request, 'doctor/create_prescription.html', context)

@login_required
def prescription_detail(request, pk):
    """View for showing prescription details"""
    try:
        prescription = get_object_or_404(
            Prescription.objects.select_related(
                'doctor',
                'doctor__user',
                'doctor__clinic',
                'patient',
                'patient__user'
            ).prefetch_related('items'),
            id=pk
        )
        
        # Check authorization
        if hasattr(request.user, 'doctor'):
            if prescription.doctor != request.user.doctor:
                messages.error(request, 'You are not authorized to view this prescription.')
                return redirect('users:doctor_dashboard')
            template = 'doctor/prescription_detail.html'
        
        elif hasattr(request.user, 'patient'):
            if prescription.patient != request.user.patient:
                messages.error(request, 'You are not authorized to view this prescription.')
                return redirect('users:patient_dashboard')
            template = 'patient/prescription_detail.html'
        
        else:
            messages.error(request, 'Access denied.')
            return redirect('users:login')
        
        # Get patient vitals
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient
        ).order_by('-recorded_at').first()
        
        context = {
            'prescription': prescription,
            'vitals': vitals,
            'patient': prescription.patient,
            'today': timezone.now(),
            'is_doctor': hasattr(request.user, 'doctor')
        }
        
        return render(request, template, context)

    except Exception as e:
        print(f"Error in prescription_detail: {str(e)}")
        messages.error(request, f'Error accessing prescription: {str(e)}')
        if hasattr(request.user, 'doctor'):
            return redirect('users:doctor_dashboard')
        return redirect('users:patient_dashboard')

@login_required
def patient_prescriptions(request, patient_id=None):
    """View for listing prescriptions - handles both doctor and patient views"""
    try:
        if hasattr(request.user, 'doctor'):
            # Doctor viewing a specific patient's prescriptions
            if patient_id:
                patient = get_object_or_404(Patient, id=patient_id)
                prescriptions = Prescription.objects.filter(
                    patient=patient,
                    doctor=request.user.doctor
                ).order_by('-created_at')
                template = 'doctor/patient_prescriptions.html'
            else:
                # Doctor viewing all their prescriptions
                prescriptions = Prescription.objects.filter(
                    doctor=request.user.doctor
                ).order_by('-created_at')
                template = 'doctor/prescriptions.html'
                patient = None
        
        elif hasattr(request.user, 'patient'):
            # Patient viewing their own prescriptions
            patient = request.user.patient
            prescriptions = Prescription.objects.filter(
                patient=patient
            ).order_by('-created_at')
            template = 'patient/prescriptions.html'
        
        else:
            messages.error(request, 'Access denied.')
            return redirect('users:login')

        context = {
            'prescriptions': prescriptions,
            'patient': patient,
            'today': timezone.now()
        }
        
        return render(request, template, context)

    except Exception as e:
        print(f"Error in patient_prescriptions: {str(e)}")
        messages.error(request, f'Error accessing prescriptions: {str(e)}')
        if hasattr(request.user, 'doctor'):
            return redirect('users:doctor_dashboard')
        return redirect('users:patient_dashboard')

@login_required
def prescriptions_view(request):
    """View for listing all prescriptions (doctor only)"""
    try:
        if not hasattr(request.user, 'doctor'):
            messages.error(request, 'Access denied. Doctor privileges required.')
            return redirect('users:dashboard')

        doctor = request.user.doctor
        prescriptions = Prescription.objects.filter(
            doctor=doctor
        ).select_related(
            'patient',
            'patient__user'
        ).order_by('-created_at')

        context = {
            'prescriptions': prescriptions,
            'doctor': doctor,
            'today': timezone.now()
        }
        
        return render(request, 'doctor/prescriptions.html', context)

    except Exception as e:
        print(f"Error in prescriptions_view: {str(e)}")
        messages.error(request, f'Error accessing prescriptions: {str(e)}')
        return redirect('users:doctor_dashboard')
