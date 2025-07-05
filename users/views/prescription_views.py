from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Prescription, Doctor, Patient, PrescriptionItem, PatientVitals, Lab, LabTest, LabTestPrescription
from labs.models import LabProfile, ExternalLabTestOffering
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
from notifications.utils import create_notification
from django.contrib.auth.models import User
import logging
from django.db import transaction
from ..forms import PrescriptionForm, VitalsForm, BasePrescriptionItemFormSet, BaseLabTestFormSet
from django.db.models import Count
from django.db.models import Q
from billing.models import Bill, BillItem
from decimal import Decimal

logger = logging.getLogger(__name__)

@login_required
@transaction.atomic # Wrap in transaction to ensure atomicity 
def create_prescription(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    doctor = get_object_or_404(Doctor, user=request.user)
    latest_vitals = PatientVitals.objects.filter(patient=patient).order_by('-created_at').first()

    if request.method == 'POST':
        vitals_form = VitalsForm(request.POST, prefix='vitals')
        prescription_form = PrescriptionForm(request.POST, prefix='prescription')
        # Instantiate formsets with POST data
        item_formset = BasePrescriptionItemFormSet(request.POST, prefix='items') 
        lab_formset = BaseLabTestFormSet(request.POST, prefix='labs')

        if vitals_form.is_valid() and prescription_form.is_valid() and item_formset.is_valid() and lab_formset.is_valid():
            try:
                # Save Vitals
                vitals = vitals_form.save(commit=False)
                # Check if any vital sign was actually entered before saving
                if any(vitals_form.cleaned_data.values()):
                    vitals.patient = patient
                    vitals.recorded_by = request.user
                    vitals.save()
                    logger.info(f"Saved vitals {vitals.id} for patient {patient_id}")
                else:
                    logger.info(f"No vitals entered for patient {patient_id}, skipping save.")
                    vitals = None # No vitals object created

                # Save Prescription
                prescription = prescription_form.save(commit=False)
                prescription.patient = patient
                prescription.doctor = doctor
                prescription.date = timezone.now()
                prescription.save()
                logger.info(f"Saved prescription {prescription.id} for patient {patient_id}")

                # Save Prescription Items (Medicines)
                items = item_formset.save(commit=False)
                for item in items:
                    item.prescription = prescription
                    item.save()
                # Handle deleted items if using can_delete=True
                for form in item_formset.deleted_forms:
                     if form.instance.pk: # Check if it's an existing item being deleted
                         form.instance.delete()
                item_formset.save_m2m() # Save any m2m if needed (not in this form)
                logger.info(f"Saved {len(items)} items for prescription {prescription.id}")

                # --- BILLING: Add prescription items to bill ---
                # Try to find the related appointment (if prescription links to one)
                appointment = getattr(prescription, 'appointment', None)
                if appointment and hasattr(appointment, 'billing_bill'):
                    bill = appointment.billing_bill
                    # Only add if bill is not finalized/paid
                    if bill.status in ['draft', 'pending', 'partial']:
                        for item in items:
                            BillItem.objects.create(
                                bill=bill,
                                item_name=f"Prescription: {item.medicine}",
                                description=f"{item.dosage or ''} {item.instructions or ''}",
                                quantity=1,
                                unit_price=getattr(item, 'price', Decimal('0.00'))
                            )
                        bill.calculate_total()
                        bill.save()

                # Process and Save Lab Tests
                lab_prescription = None
                processed_labs = [] # To store successfully created LabTest objects
                if lab_formset.has_changed(): # Check if any lab forms have data
                    lab_prescription = LabTestPrescription.objects.create(
                        doctor=request.user,
                        patient=patient,
                        notes="", # Add field for lab notes if needed
                        preferred_lab_type='PATIENT_CHOICE' # Or get from form
                    )
                    logger.info(f"Created LabTestPrescription {lab_prescription.id} for patient {patient_id}")
                    
                    for form in lab_formset:
                        if form.is_valid() and form.has_changed() and not form.cleaned_data.get('DELETE'):
                            lab_data = form.cleaned_data
                            combined_lab_id = lab_data['lab_id']
                            test_name = lab_data['test_name']
                            
                            # Parse lab_type and lab_pk from the combined_lab_id
                            try:
                                lab_type, lab_pk_str = combined_lab_id.split('-', 1)
                                lab_pk = int(lab_pk_str)
                            except (ValueError, TypeError):
                                messages.error(request, f"Invalid lab identifier format for test '{test_name}'. Please re-select the lab.")
                                # Rollback transaction by raising error
                                raise ValueError("Invalid lab identifier format.") 

                            test_definition = None
                            lab_display_name = "Unknown Lab"

                            try:
                                if lab_type == 'internal':
                                    lab = get_object_or_404(Lab, pk=lab_pk)
                                    lab_display_name = lab.name
                                    test_definition = lab.test_definitions.filter(name=test_name).first()
                                    if not test_definition:
                                        messages.error(request, f"Internal Lab '{lab.name}' does not offer test: '{test_name}'.")
                                        raise ValueError(f"Test not offered by internal lab {lab.name}")
                                
                                elif lab_type == 'external':
                                    lab_profile = get_object_or_404(LabProfile, pk=lab_pk, is_approved=True)
                                    lab_display_name = lab_profile.name
                                    test_offering = ExternalLabTestOffering.objects.filter(
                                        lab_profile=lab_profile,
                                        test__name=test_name,
                                        is_active=True
                                    ).select_related('test').first()
                                    if not test_offering:
                                        messages.error(request, f"External Lab '{lab_profile.name}' does not offer test: '{test_name}'.")
                                        raise ValueError(f"Test not offered by external lab {lab_profile.name}")
                                    test_definition = test_offering.test
                                else:
                                    messages.error(request, f"Invalid lab type '{lab_type}' for test '{test_name}'.")
                                    raise ValueError("Invalid lab type specified.")

                                # Create LabTest object
                                lab_test = LabTest.objects.create(
                                    prescription=lab_prescription,
                                    test_definition=test_definition,
                                    status='REQUESTED',
                                    collection_type=lab_data['collection_type'],
                                    doctor_notes=lab_data.get('description', '')
                                )
                                processed_labs.append({'lab_test': lab_test, 'lab_type': lab_type, 'lab_pk': lab_pk, 'lab_name': lab_display_name})
                                logger.info(f"Saved LabTest for '{test_name}' (Lab: {lab_display_name}) for prescription {prescription.id}")
                                
                                if lab_type == 'external':
                                    lab_prescription.external_lab = lab_profile
                                    lab_prescription.save()
                            
                            except (Lab.DoesNotExist, LabProfile.DoesNotExist):
                                messages.error(request, f"Selected lab (Type: {lab_type}, ID: {lab_pk}) not found or not approved for test '{test_name}'.")
                                raise ValueError("Lab not found or not approved.")
                            except Exception as e: # Catch other errors during test definition lookup/saving
                                logger.error(f"Error processing lab test '{test_name}' for lab {lab_pk} ({lab_type}): {e}")
                                messages.error(request, f"An error occurred while processing lab test '{test_name}'.")
                                raise e # Reraise to trigger transaction rollback

                # --- Notifications --- (Keep existing notification logic, adjust as needed)
                # Notify Patient
                try:
                    if prescription.patient and prescription.patient.user:
                        create_notification(
                            user=prescription.patient.user,
                            message=f"Dr. {prescription.doctor.name} has created a new prescription for you. View in portal.",
                            notification_type='prescription_new'
                        )
                    else:
                        logger.warning(f"Patient {patient_id} has no associated user account. Skipping notification.")
                except Exception as e:
                    logger.error(f"Error creating patient prescription notification: {e}", exc_info=True)
                    # Don't rollback, just warn
                    messages.warning(request, "Prescription saved, but failed to send patient notification.")

                # Notify Labs 
                if lab_prescription and processed_labs:
                    notified_labs = set() # (lab_type, lab_pk)
                    for lab_info in processed_labs:
                        lab_key = (lab_info['lab_type'], lab_info['lab_pk'])
                        if lab_key in notified_labs: 
                            continue
                        
                        message_detail = f"New lab test request from Dr. {doctor.name}. Patient: {patient.get_full_name()}. Test: {lab_info['lab_test'].test_definition.name}"
                        try:
                            if lab_info['lab_type'] == 'internal':
                                # Get all lab staff for the clinic
                                clinic_recipients = User.objects.filter(
                                    Q(staff__clinic=doctor.clinic, staff__role='lab_technician') |
                                    Q(staff__clinic=doctor.clinic, staff__is_admin=True)
                                ).distinct()
                                
                                if clinic_recipients.exists():
                                    for recipient in clinic_recipients:
                                        if recipient:  # Check that recipient is not None
                                            create_notification(
                                                user=recipient,
                                                message=f"{message_detail} for internal lab {lab_info['lab_name']}. Collection type: {lab_info['lab_test'].get_collection_type_display()}. {lab_info['lab_test'].doctor_notes or ''}",
                                                notification_type='lab_test_new'
                                            )
                                    notified_labs.add(lab_key)
                                    logger.info(f"Successfully sent notifications to {clinic_recipients.count()} internal lab staff for {lab_info['lab_name']}")
                                else:
                                    logger.warning(f"No lab staff found for clinic {doctor.clinic.id} to notify for lab {lab_info['lab_name']}.")
                            
                            elif lab_info['lab_type'] == 'external':
                                try:
                                    lab_profile = LabProfile.objects.select_related('user').get(pk=lab_info['lab_pk'])
                                    if lab_profile and lab_profile.user:
                                        create_notification(
                                            user=lab_profile.user,
                                            message=f"{message_detail} for your lab {lab_info['lab_name']}. Collection type: {lab_info['lab_test'].get_collection_type_display()}. {lab_info['lab_test'].doctor_notes or ''}",
                                            notification_type='lab_test_new'
                                        )
                                        notified_labs.add(lab_key)
                                        logger.info(f"Successfully sent notification to external lab {lab_info['lab_name']}")
                                    else:
                                        logger.warning(f"External LabProfile {lab_info['lab_pk']} has no user to notify.")
                                except LabProfile.DoesNotExist:
                                    logger.error(f"LabProfile with id {lab_info['lab_pk']} not found")
                                    messages.warning(request, f"Prescription saved, but failed to send notification for lab {lab_info['lab_name']} (lab not found).")
                        
                        except Exception as e:
                            logger.error(f"Error sending notification for lab {lab_key}: {e}", exc_info=True)
                            # Don't rollback, just warn
                            messages.warning(request, f"Prescription saved, but failed to send notification for lab {lab_info['lab_name']}")

                messages.success(request, 'Prescription created successfully')
                return redirect('users:prescription_detail', pk=prescription.id)

            except Exception as e: # Catch errors during saving or processing
                logger.error(f"Error during prescription creation process: {e}", exc_info=True)
                # Transaction automatically rolls back here due to the raised exception or this catch
                messages.error(request, f'An unexpected error occurred: {str(e)}. Please try again.')
                # Re-render form with errors below

        else: # Forms are not valid
            # Log form errors for debugging
            logger.warning(f"Prescription form errors: Vitals={vitals_form.errors} Prescription={prescription_form.errors} Items={item_formset.errors} Labs={lab_formset.errors}")
            messages.error(request, 'Please correct the errors below.')

    else: # GET request
        vitals_form = VitalsForm(prefix='vitals', instance=latest_vitals) # Pre-fill vitals
        prescription_form = PrescriptionForm(prefix='prescription')
        item_formset = BasePrescriptionItemFormSet(prefix='items', queryset=PrescriptionItem.objects.none()) # Empty formset for GET
        lab_formset = BaseLabTestFormSet(prefix='labs') # Empty formset for GET

    # Get available labs (needed for both GET and POST error re-render)
    internal_labs = Lab.objects.filter(clinic=doctor.clinic).values('id', 'name')
    external_labs = LabProfile.objects.filter(is_approved=True).values('id', 'name')
    # Combine labs for JavaScript, adding type info
    available_labs_json = json.dumps(
        [{'id': lab['id'], 'name': lab['name'], 'type': 'internal'} for lab in internal_labs] + 
        [{'id': lab['id'], 'name': lab['name'], 'type': 'external'} for lab in external_labs]
    )

    context = {
        'patient': patient,
        'doctor': doctor,
        'vitals_form': vitals_form,
        'prescription_form': prescription_form,
        'item_formset': item_formset,
        'lab_formset': lab_formset,
        'available_labs_json': available_labs_json, # Pass labs as JSON for JS
        'has_lab': internal_labs.exists() or external_labs.exists(),
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
        lab_prescriptions = LabTestPrescription.objects.filter(
            patient=prescription.patient,
            doctor=prescription.doctor.user,
            prescription_date__date=prescription.created_at.date()
        )
        
        lab_tests = []
        for lab_prescription in lab_prescriptions:
            lab_tests.extend(LabTest.objects.filter(prescription=lab_prescription).select_related('test_definition'))
        
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

