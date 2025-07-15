from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.db import transaction
from django.db.models import Count, Q
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from xhtml2pdf import pisa
from io import BytesIO
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any
import os
import json
import logging

# Local imports
from ..models import (
    Prescription, Doctor, Patient, PrescriptionItem, 
    PatientVitals, Lab, LabTest, LabTestPrescription, PrescriptionTemplate
)
from ..serializers import PrescriptionSerializer
from ..forms import PrescriptionForm, VitalsForm, BasePrescriptionItemFormSet, BaseLabTestFormSet
from labs.models import LabProfile, ExternalLabTestOffering, TestDefinition
from billing.models import Bill, BillItem
from notifications.utils import create_notification

logger = logging.getLogger(__name__)

@login_required
def prescription_selection(request, patient_id):
    """View for selecting between classic and modern prescription interfaces"""
    patient = get_object_or_404(Patient, id=patient_id)
    
    # Ensure the request user is linked to a Doctor profile
    try:
        doctor = Doctor.objects.select_related('user', 'clinic').get(user=request.user)
    except Doctor.DoesNotExist:
        messages.error(request, "Your user account is not associated with a doctor profile.")
        return redirect('users:doctor_dashboard')
    
    context = {
        'patient': patient,
        'doctor': doctor,
    }
    return render(request, 'doctor/prescription_selection.html', context)

@login_required
def create_prescription_modern(request, patient_id):
    """Modern prescription creation view with enhanced features"""
    logger.info(f"Starting modern prescription creation for patient {patient_id}")
    
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        logger.info(f"Found patient: {patient.id} - {patient.user.get_full_name() if patient.user else 'No user'}")
    except Exception as e:
        logger.error(f"Error finding patient {patient_id}: {e}")
        messages.error(request, 'Patient not found.')
        return redirect('users:doctor_dashboard')
    
    # Ensure the request user is linked to a Doctor profile
    try:
        doctor = Doctor.objects.select_related('user', 'clinic').get(user=request.user)
    except Doctor.DoesNotExist:
        messages.error(request, "Your user account is not associated with a doctor profile.")
        return redirect('users:doctor_dashboard')
    
    latest_vitals = PatientVitals.objects.filter(patient=patient).order_by('-created_at').first()
    
    if request.method == 'POST':
        # Use transaction.atomic() as a context manager for better error handling
        try:
            with transaction.atomic():
                # Extract form data
                chief_complaints = request.POST.get('chief_complaints', '').strip()
                clinical_findings = request.POST.get('clinical_findings', '').strip()
                diagnosis = request.POST.get('diagnosis', '').strip()
                advice = request.POST.get('advice', '').strip()
                follow_up_date = request.POST.get('follow_up_date', '').strip()
                
                # Extract vitals data
                blood_pressure = request.POST.get('blood_pressure', '').strip()
                temperature = request.POST.get('temperature', '').strip()
                weight = request.POST.get('weight', '').strip()
                heart_rate = request.POST.get('heart_rate', '').strip()
                
                # Validate required fields
                if not chief_complaints:
                    messages.error(request, 'Chief complaints are required.')
                    raise ValueError('Chief complaints are required.')
                
                if not diagnosis:
                    messages.error(request, 'Diagnosis is required.')
                    raise ValueError('Diagnosis is required.')
                
                # Save vitals if provided
                saved_vitals = None
                if any([blood_pressure, temperature, weight, heart_rate]):
                    try:
                        saved_vitals = PatientVitals.objects.create(
                            patient=patient,
                            recorded_by=request.user,
                            blood_pressure=blood_pressure or None,
                            temperature=temperature or None,
                            weight=weight or None,
                            heart_rate=heart_rate or None,
                        )
                        logger.info(f"Saved vitals {saved_vitals.id} for patient {patient.id}")
                    except Exception as e:
                        logger.error(f"Error saving vitals: {e}")
                        # Continue without vitals if there's an error
                
                # Create prescription
                try:
                    prescription = Prescription.objects.create(
                        patient=patient,
                        doctor=doctor,
                        chief_complaints=chief_complaints,
                        clinical_findings=clinical_findings,
                        diagnosis=diagnosis,
                        advice=advice,
                        date=timezone.now().date(),  # Explicitly set the date field
                        follow_up_date=follow_up_date if follow_up_date else None,
                    )
                    logger.info(f"Created prescription {prescription.id} for patient {patient.id}")
                except Exception as e:
                    logger.error(f"Error creating prescription: {e}")
                    raise
                
                # Process medicines
                medicine_count = 0
                while f'medicines[{medicine_count}][name]' in request.POST:
                    medicine_name = request.POST.get(f'medicines[{medicine_count}][name]', '').strip()
                    if medicine_name:  # Only save if medicine name is provided
                        try:
                            dosage = request.POST.get(f'medicines[{medicine_count}][dosage]', '').strip()
                            duration = request.POST.get(f'medicines[{medicine_count}][duration]', '').strip()
                            frequency = request.POST.get(f'medicines[{medicine_count}][frequency]', '').strip()
                            instructions = request.POST.get(f'medicines[{medicine_count}][instructions]', '').strip()
                            
                            # Create prescription item
                            # Handle duration field - convert string to integer or use default
                            try:
                                duration_value = int(duration) if duration and duration.isdigit() else 30
                            except (ValueError, AttributeError):
                                duration_value = 30  # Default to 30 days if invalid
                            
                            PrescriptionItem.objects.create(
                                prescription=prescription,
                                medicine=medicine_name,
                                dosage=dosage,
                                duration=duration_value,
                                duration_unit='days',  # Use lowercase to match model choices
                                instructions=instructions,
                            )
                        except Exception as e:
                            logger.error(f"Error creating prescription item for {medicine_name}: {e}")
                            # Continue with other medicines
                    medicine_count += 1
                
                # Process lab tests (if any) - moved outside transaction to prevent rollback
                lab_tests_to_create = []
                lab_count = 0
                
                # Debug: Log all POST data related to lab tests
                logger.info("=== LAB TESTS DEBUG ===")
                for key, value in request.POST.items():
                    if 'lab_tests' in key:
                        logger.info(f"Lab test POST data: {key} = {value}")
                
                while f'lab_tests[{lab_count}][name]' in request.POST:
                    test_name = request.POST.get(f'lab_tests[{lab_count}][name]', '').strip()
                    if test_name:
                        collection_type = request.POST.get(f'lab_tests[{lab_count}][collection_type]', 'CLINIC')
                        description = request.POST.get(f'lab_tests[{lab_count}][description]', '').strip()
                        
                        lab_tests_to_create.append({
                            'test_name': test_name,
                            'collection_type': collection_type,
                            'description': description
                        })
                        logger.info(f"Added lab test to create: {test_name}")
                    lab_count += 1
                
                logger.info(f"Total lab tests to create: {len(lab_tests_to_create)}")
                logger.info("=== END LAB TESTS DEBUG ===")
                
                # Ensure prescription is saved and get the ID
                prescription_id = prescription.id
                logger.info(f"Prescription created with ID: {prescription_id}")
                
                messages.success(request, 'Prescription created successfully using modern interface!')
                
                # Create lab tests outside the transaction block
                if lab_tests_to_create:
                    try:
                        # Create a new lab test prescription specifically for this prescription
                        lab_prescription = LabTestPrescription.objects.create(
                            doctor=doctor.user,
                            patient=patient,
                            preferred_lab_type='PATIENT_CHOICE',
                            prescription_date=prescription.created_at  # Explicitly set to prescription creation time
                        )
                        
                        for lab_test_data in lab_tests_to_create:
                            try:
                                # Get or create test definition
                                test_definition, created = TestDefinition.objects.get_or_create(
                                    name=lab_test_data['test_name']
                                )
                                
                                # Create lab test
                                LabTest.objects.create(
                                    prescription=lab_prescription,
                                    test_definition=test_definition,
                                    status='REQUESTED',
                                    collection_type=lab_test_data['collection_type'],
                                    doctor_notes=lab_test_data['description'],
                                )
                                logger.info(f"Created lab test: {lab_test_data['test_name']} for prescription {prescription.id}")
                            except Exception as e:
                                logger.error(f"Error creating lab test {lab_test_data['test_name']}: {e}")
                                # Continue with other lab tests
                    except Exception as e:
                        logger.error(f"Error creating lab test prescription: {e}")
                
                logger.info(f"Redirecting to prescription detail with ID: {prescription_id}")
                return redirect('users:prescription_detail', pk=prescription_id)
                
        except ValueError as e:
            # Validation errors - transaction already rolled back
            logger.warning(f"Validation error in prescription creation: {e}")
            # Don't add another error message since it's already added above
            
        except Exception as e:
            # Other errors - transaction already rolled back
            logger.error(f"Error creating prescription: {e}", exc_info=True)
            messages.error(request, f'An error occurred while saving the prescription. Please try again.')
    
    # Prepare context with latest vitals data
    context = {
        'patient': patient,
        'doctor': doctor,
        'latest_vitals': latest_vitals,
        'vitals_data': {
            'blood_pressure': latest_vitals.blood_pressure if latest_vitals else '',
            'temperature': latest_vitals.temperature if latest_vitals else '',
            'weight': latest_vitals.weight if latest_vitals else '',
            'heart_rate': latest_vitals.heart_rate if latest_vitals else '',
        } if latest_vitals else {},
    }
    
    return render(request, 'doctor/create_prescription_modern.html', context)

@login_required
@require_http_methods(["POST"])
def save_prescription_draft(request):
    """Save prescription as draft"""
    try:
        # Extract form data
        form_data = request.POST.dict()
        
        # Create a draft prescription object (you might want to create a separate DraftPrescription model)
        # For now, we'll store it in session or create a temporary record
        
        # Store draft data in session
        draft_data = {
            'chief_complaints': form_data.get('chief_complaints', ''),
            'clinical_findings': form_data.get('clinical_findings', ''),
            'diagnosis': form_data.get('diagnosis', ''),
            'advice': form_data.get('advice', ''),
            'follow_up_date': form_data.get('follow_up_date', ''),
            'medicines': [],
            'lab_tests': [],
            'vitals': {
                'blood_pressure': form_data.get('blood_pressure', ''),
                'temperature': form_data.get('temperature', ''),
                'weight': form_data.get('weight', ''),
                'heart_rate': form_data.get('heart_rate', ''),
            },
            'timestamp': datetime.now().isoformat(),
        }
        
        # Extract medicines from form data
        medicine_count = 0
        while f'medicines[{medicine_count}][name]' in form_data:
            medicine_data = {
                'name': form_data.get(f'medicines[{medicine_count}][name]', ''),
                'dosage': form_data.get(f'medicines[{medicine_count}][dosage]', ''),
                'duration': form_data.get(f'medicines[{medicine_count}][duration]', ''),
                'frequency': form_data.get(f'medicines[{medicine_count}][frequency]', ''),
                'instructions': form_data.get(f'medicines[{medicine_count}][instructions]', ''),
            }
            if medicine_data['name']:  # Only add if medicine name is provided
                draft_data['medicines'].append(medicine_data)
            medicine_count += 1
        
        # Store in session
        request.session['prescription_draft'] = draft_data
        
        return JsonResponse({
            'success': True,
            'message': 'Draft saved successfully',
            'timestamp': draft_data['timestamp']
        })
        
    except Exception as e:
        logger.error(f"Error saving draft: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Error saving draft'
        }, status=500)

@login_required
def load_prescription_draft(request):
    """Load saved prescription draft"""
    try:
        draft_data = request.session.get('prescription_draft')
        if draft_data:
            return JsonResponse({
                'success': True,
                'data': draft_data
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No draft found'
            })
    except Exception as e:
        logger.error(f"Error loading draft: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Error loading draft'
        }, status=500)

@login_required
def prescription_detail(request, pk):
    """View for showing prescription details"""
    logger.info(f"Attempting to access prescription with ID: {pk}")
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
        logger.info(f"Found prescription: {prescription.id} for patient {prescription.patient.id}")
        
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
            # Set the template for patient view
            template = 'patient/prescription_detail.html' 
        
        else:
            messages.error(request, 'Access denied.')
            return redirect('users:login')
        
        # Get patient vitals
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient
        ).order_by('-created_at').first()

        # Get lab tests created with this prescription
        # Look for lab tests created on the same date as the prescription
        lab_prescriptions = LabTestPrescription.objects.filter(
            patient=prescription.patient,
            doctor=prescription.doctor.user,
            prescription_date__date=prescription.created_at.date()
        )
        
        # Also look for lab tests created within a reasonable time window (same day)
        if not lab_prescriptions.exists():
            # Fallback: look for lab tests created on the same day
            lab_prescriptions = LabTestPrescription.objects.filter(
                patient=prescription.patient,
                doctor=prescription.doctor.user,
                prescription_date__date=prescription.date
            )
        
        # Additional fallback: look for lab tests created within 1 hour of prescription creation
        if not lab_prescriptions.exists():
            from datetime import timedelta
            
            # Look for lab prescriptions created within 1 hour before or after prescription creation
            time_window_start = prescription.created_at - timedelta(hours=1)
            time_window_end = prescription.created_at + timedelta(hours=1)
            
            lab_prescriptions = LabTestPrescription.objects.filter(
                patient=prescription.patient,
                doctor=prescription.doctor.user,
                prescription_date__range=(time_window_start, time_window_end)
            )
        
        lab_tests = []
        for lab_prescription in lab_prescriptions:
            lab_tests.extend(LabTest.objects.filter(prescription=lab_prescription).select_related('test_definition'))
        
        # Debug logging
        logger.info(f"Found {len(lab_prescriptions)} lab prescriptions for prescription {prescription.id}")
        logger.info(f"Found {len(lab_tests)} lab tests for prescription {prescription.id}")
        
        # Log the lab test names for debugging
        for lab_test in lab_tests:
            logger.info(f"Lab test found: {lab_test.test_definition.name if lab_test.test_definition else 'Unknown'}")
        
        context = {
            'prescription': prescription,
            'vitals': vitals,
            'patient': prescription.patient,
            'today': timezone.now(),
            'is_doctor': hasattr(request.user, 'doctor'),
            'lab_tests': lab_tests
        }
        
        # Debug: Print context to console
        print(f"DEBUG: Prescription {prescription.id} context:")
        print(f"DEBUG: Lab tests count: {len(lab_tests)}")
        print(f"DEBUG: Lab tests: {[lt.test_definition.name if lt.test_definition else 'Unknown' for lt in lab_tests]}")
        
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_diagnosis_drug_suggestions(request):
    """
    API endpoint to suggest medicines based on doctor's past prescriptions 
    for a given diagnosis term.
    Expects a 'diagnosis' query parameter.
    """
    if not hasattr(request.user, 'doctor'):
        return Response({'error': 'User is not a doctor'}, status=status.HTTP_403_FORBIDDEN)

    doctor = request.user.doctor
    diagnosis_query = request.query_params.get('diagnosis', '').strip()

    if not diagnosis_query or len(diagnosis_query) < 3: # Require minimum length
        return Response({'suggestions': []}, status=status.HTTP_200_OK) 
        # Return empty list if query is too short or empty, not an error

    try:
        # Find prescriptions by this doctor matching the diagnosis term (case-insensitive)
        # Aggregate the count of each medicine prescribed for those diagnoses.
        suggestions = PrescriptionItem.objects.filter(
            prescription__doctor=doctor,
            prescription__diagnosis__icontains=diagnosis_query
        ).values(
            'medicine' # Group by medicine name
        ).annotate(
            frequency=Count('medicine') # Count occurrences
        ).order_by(
            '-frequency', 'medicine' # Order by most frequent first, then alphabetically
        ).values_list(
            'medicine', flat=True # Select only the medicine name
        )[:10] # Limit to top 10 suggestions

        return Response({'suggestions': list(suggestions)}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error fetching diagnosis drug suggestions for doctor {doctor.id} and diagnosis '{diagnosis_query}': {e}", exc_info=True)
        return Response({'error': 'Failed to fetch suggestions'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
@require_http_methods(["POST"])
def delete_prescription_item(request, prescription_id, item_id):
    """Delete a prescription item (medicine)"""
    try:
        prescription = get_object_or_404(Prescription, id=prescription_id)
        
        # Check authorization
        if hasattr(request.user, 'doctor'):
            if prescription.doctor != request.user.doctor:
                return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
        
        # Delete the prescription item
        item = get_object_or_404(PrescriptionItem, id=item_id, prescription=prescription)
        item.delete()
        
        return JsonResponse({'success': True, 'message': 'Medicine deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting prescription item: {e}")
        return JsonResponse({'success': False, 'message': 'Error deleting medicine'}, status=500)

@login_required
@require_http_methods(["POST"])
def edit_prescription_item(request, prescription_id, item_id):
    """Edit a prescription item (medicine)"""
    try:
        prescription = get_object_or_404(Prescription, id=prescription_id)
        
        # Check authorization
        if hasattr(request.user, 'doctor'):
            if prescription.doctor != request.user.doctor:
                return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
        
        # Get the prescription item
        item = get_object_or_404(PrescriptionItem, id=item_id, prescription=prescription)
        
        if request.method == 'POST':
            # Update the item
            item.medicine = request.POST.get('medicine', item.medicine)
            item.dosage = request.POST.get('dosage', item.dosage)
            item.duration = int(request.POST.get('duration', item.duration))
            item.duration_unit = request.POST.get('duration_unit', item.duration_unit)
            item.instructions = request.POST.get('instructions', item.instructions)
            item.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Medicine updated successfully',
                'item': {
                    'id': item.id,
                    'medicine': item.medicine,
                    'dosage': item.dosage,
                    'duration': item.duration,
                    'duration_unit': item.duration_unit,
                    'instructions': item.instructions
                }
            })
        
        # Return current item data for editing
        return JsonResponse({
            'success': True,
            'item': {
                'id': item.id,
                'medicine': item.medicine,
                'dosage': item.dosage,
                'duration': item.duration,
                'duration_unit': item.duration_unit,
                'instructions': item.instructions
            }
        })
        
    except Exception as e:
        logger.error(f"Error editing prescription item: {e}")
        return JsonResponse({'success': False, 'message': 'Error editing medicine'}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_lab_test(request, prescription_id, lab_test_id):
    """Delete a lab test"""
    try:
        prescription = get_object_or_404(Prescription, id=prescription_id)
        
        # Check authorization
        if hasattr(request.user, 'doctor'):
            if prescription.doctor != request.user.doctor:
                return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
        
        # Delete the lab test
        lab_test = get_object_or_404(LabTest, id=lab_test_id)
        lab_test.delete()
        
        return JsonResponse({'success': True, 'message': 'Lab test deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting lab test: {e}")
        return JsonResponse({'success': False, 'message': 'Error deleting lab test'}, status=500)

@login_required
@require_http_methods(["POST"])
def edit_lab_test(request, prescription_id, lab_test_id):
    """Edit a lab test"""
    try:
        prescription = get_object_or_404(Prescription, id=prescription_id)
        
        # Check authorization
        if hasattr(request.user, 'doctor'):
            if prescription.doctor != request.user.doctor:
                return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
        
        # Get the lab test
        lab_test = get_object_or_404(LabTest, id=lab_test_id)
        
        if request.method == 'POST':
            # Update the lab test
            lab_test.collection_type = request.POST.get('collection_type', lab_test.collection_type)
            lab_test.doctor_notes = request.POST.get('doctor_notes', lab_test.doctor_notes)
            lab_test.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Lab test updated successfully',
                'lab_test': {
                    'id': lab_test.id,
                    'test_name': lab_test.test_definition.name,
                    'collection_type': lab_test.collection_type,
                    'doctor_notes': lab_test.doctor_notes,
                    'status': lab_test.status
                }
            })
        
        # Return current lab test data for editing
        return JsonResponse({
            'success': True,
            'lab_test': {
                'id': lab_test.id,
                'test_name': lab_test.test_definition.name,
                'collection_type': lab_test.collection_type,
                'doctor_notes': lab_test.doctor_notes,
                'status': lab_test.status
            }
        })
        
    except Exception as e:
        logger.error(f"Error editing lab test: {e}")
        return JsonResponse({'success': False, 'message': 'Error editing lab test'}, status=500)

