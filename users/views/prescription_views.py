from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Prescription, Doctor, Patient, PrescriptionItem, PatientVitals, Lab, LabTest
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
from rest_framework.views import APIView
from django.views import View
from datetime import date


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

            # Handle lab tests
            lab_tests_data = json.loads(request.POST.get('lab_tests', '[]'))
            clinic_lab = Lab.objects.filter(clinic=doctor.clinic).first()
            
            for test_data in lab_tests_data:
                LabTest.objects.create(
                    patient=patient,
                    doctor=doctor,
                    lab=clinic_lab,
                    test_name=test_data['test_name'],
                    description=test_data['description'],
                    collection_type=test_data['collection_type'],
                    status='REQUESTED'
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
    latest_vitals = PatientVitals.objects.filter(patient=patient).order_by('-created_at').first()

    context = {
        'patient': patient,
        'doctor': doctor,
        'vitals': latest_vitals,
        'has_lab': Lab.objects.filter(clinic=doctor.clinic).exists()
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
        ).order_by('-created_at').first()

        # Get lab tests created with this prescription
        lab_tests = LabTest.objects.filter(
            patient=prescription.patient,
            doctor=prescription.doctor,
            created_at__date=prescription.created_at.date()
        ).order_by('created_at')
        
        context = {
            'prescription': prescription,
            'vitals': vitals,
            'patient': prescription.patient,
            'today': timezone.now(),
            'is_doctor': hasattr(request.user, 'doctor'),
            'lab_tests': lab_tests
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

class PatientPrescriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get prescriptions for the logged-in patient."""
        try:
            patient = request.user.patient
            prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
            serializer = PrescriptionSerializer(prescriptions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error fetching prescriptions: {str(e)}")
            return Response({"error": "Failed to fetch prescriptions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreatePrescriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Create a new prescription."""
        serializer = PrescriptionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PrescriptionListView(View):
    def get(self, request):
        """Render the list of prescriptions for the logged-in patient."""
        try:
            patient = request.user.patient
            prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
            return render(request, 'patient/prescriptions.html', {'prescriptions': prescriptions})
        except Exception as e:
            print(f"Error fetching prescriptions: {str(e)}")
            return render(request, 'error.html', {'message': 'Failed to fetch prescriptions'})
@login_required
class DoctorPatientPrescriptionsView(APIView):
    permission_classes = [IsAuthenticated]
    csrf_exempt = True
    def get(self, request, patient_id):
        """Get prescriptions for a specific patient (doctor only)."""
        try:
            if not hasattr(request.user, 'doctor'):
                return Response({"error": "Doctor privileges required"}, status=status.HTTP_403_FORBIDDEN)
            
            patient = get_object_or_404(Patient, id=patient_id)
            prescriptions = Prescription.objects.filter(
                patient=patient,
                doctor=request.user.doctor
            ).select_related(
                'patient',
                'patient__user'
            ).prefetch_related('items').order_by('-created_at')
            
            serializer = PrescriptionSerializer(prescriptions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error fetching prescriptions: {str(e)}")
            return Response({"error": "Failed to fetch prescriptions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prescription_detail_api(request, pk):
    """API view for prescription details"""
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
                return Response({'error': 'Unauthorized access'}, status=403)
        
        elif hasattr(request.user, 'patient'):
            if prescription.patient != request.user.patient:
                return Response({'error': 'Unauthorized access'}, status=403)
        
        else:
            return Response({'error': 'Access denied'}, status=403)

        # Get patient vitals
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient
        ).order_by('-created_at').first()

        # Calculate age from birthdate
        today = date.today()
        birthdate = prescription.patient.date_of_birth
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

        # Format the response data
        data = {
            'id': prescription.id,
            'created_at': prescription.created_at.strftime('%Y-%m-%d'),
            'doctor_name': f"{prescription.doctor.user.first_name} {prescription.doctor.user.last_name}",
            'doctor_qualification': prescription.doctor.qualification,
            'doctor_registration_number': prescription.doctor.license_number,
            'clinic_id': prescription.doctor.clinic.id if prescription.doctor.clinic else None,
            'patient_name': f"{prescription.patient.user.first_name} {prescription.patient.user.last_name}",
            'patient_gender': prescription.patient.gender,
            'patient_age': age,
            'patient_mobile': prescription.patient.phone_number,
            'patient_address': prescription.patient.address,
            'patient_weight': vitals.weight if vitals else None,
            'patient_height': vitals.height if vitals else None,
            'patient_bmi': vitals.bmi if vitals else None,
            'patient_bp': vitals.blood_pressure if vitals else None,
            'chief_complaints': prescription.chief_complaints,
            'clinical_findings': prescription.clinical_findings,
            'diagnosis': prescription.diagnosis,
            'advice': prescription.advice,
            'follow_up_date': prescription.follow_up_date.strftime('%Y-%m-%d') if prescription.follow_up_date else None,
            'medicines': [{
                'name': item.medicine,
                'dosage': item.dosage,
                'duration': item.duration,
                'instructions': item.instructions
            } for item in prescription.items.all()]
        }
        
        return Response(data)

    except Exception as e:
        print(f"Error in prescription_detail_api: {str(e)}")
        return Response({'error': str(e)}, status=500)
