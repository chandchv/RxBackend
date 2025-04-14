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

logger = logging.getLogger(__name__)

@login_required
def create_prescription(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    doctor = get_object_or_404(Doctor, user=request.user)
    
    if request.method == 'POST':
        try:
            # Create patient vitals
            vitals = PatientVitals.objects.create(
                patient=patient,
                weight=float(request.POST.get('weight', 0)),
                height=float(request.POST.get('height', 0)),
                blood_pressure=request.POST.get('blood_pressure'),
                temperature=float(request.POST.get('temperature', 0)),
                heart_rate=float(request.POST.get('heart_rate', 0)),
                oxygen_saturation=float(request.POST.get('oxygen_saturation', 0)),
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
            lab_prescription = None # Initialize
            
            if lab_tests_data:
                # Create a lab test prescription
                lab_prescription = LabTestPrescription.objects.create(
                    doctor=request.user, # Use the actual user object
                    patient=patient,
                    notes=request.POST.get('lab_notes', ''),
                    preferred_lab_type='PATIENT_CHOICE' # Example, adjust if needed
                )
                
                for test_data in lab_tests_data:
                    lab_id = test_data.get('lab_id')
                    lab_type = test_data.get('lab_type')
                    test_name = test_data.get('test_name', 'Unknown Test')
                    
                    if not lab_id or not lab_type:
                        messages.error(request, 'Missing lab ID or type for a test.')
                        # Consider rolling back or handling differently
                        return redirect('users:create_prescription', patient_id=patient_id) 
                    
                    try:
                        if lab_type == 'internal':
                            lab = get_object_or_404(Lab, id=lab_id)
                            test_definition = lab.test_definitions.filter(name=test_name).first()
                            if not test_definition:
                                messages.error(request, f"Internal Lab {lab.name} does not offer: {test_name}")
                                return redirect('users:create_prescription', patient_id=patient_id)
                            
                            LabTest.objects.create(
                                prescription=lab_prescription,
                                test_definition=test_definition,
                                status='REQUESTED',
                                collection_type=test_data.get('collection_type', 'CLINIC'),
                                doctor_notes=test_data.get('description', '')
                            )
                        elif lab_type == 'external':
                            lab_profile = get_object_or_404(LabProfile, id=lab_id, is_approved=True)
                            test_offering = ExternalLabTestOffering.objects.filter(
                                lab_profile=lab_profile,
                                test__name=test_name,
                                is_active=True
                            ).select_related('test').first()
                            
                            if not test_offering:
                                messages.error(request, f"External Lab {lab_profile.name} does not offer: {test_name}")
                                return redirect('users:create_prescription', patient_id=patient_id)
                            
                            LabTest.objects.create(
                                prescription=lab_prescription,
                                test_definition=test_offering.test,
                                status='REQUESTED',
                                collection_type=test_data.get('collection_type', 'LAB'),
                                doctor_notes=test_data.get('description', '')
                            )
                        else:
                             messages.error(request, f"Invalid lab type specified: {lab_type}")
                             return redirect('users:create_prescription', patient_id=patient_id)
                             
                    except (Lab.DoesNotExist, LabProfile.DoesNotExist):
                        messages.error(request, f"Selected lab (Type: {lab_type}, ID: {lab_id}) not found or not approved.")
                        return redirect('users:create_prescription', patient_id=patient_id)
                    except Exception as e:
                        logger.error(f"Error creating LabTest for {test_name}: {e}")
                        messages.error(request, f"An error occurred while adding lab test {test_name}.")
                        return redirect('users:create_prescription', patient_id=patient_id)

            # --- Notifications --- 
            # Notify Patient about the Prescription
            try:
                create_notification(
                    recipient=prescription.patient.user,
                    message=f"Dr. {prescription.doctor.name} has created a new prescription for you. You can view it in your portal.",
                    sender=request.user, 
                    notification_type='prescription_new',
                    related_object=prescription
                )
            except Exception as e:
                logger.error(f"Error creating patient prescription notification: {e}")
                messages.warning(request, "Prescription created, but failed to send patient notification.")

            # Notify Labs if tests were prescribed
            if lab_prescription: 
                notified_labs = set() # Keep track of notified labs (type, id)
                try:
                    for test_data in lab_tests_data: # Re-iterate to easily get lab details for notification
                        lab_id = test_data.get('lab_id')
                        lab_type = test_data.get('lab_type')
                        test_name = test_data.get('test_name', 'Unknown Test')
                        
                        if not lab_id or not lab_type: continue
                        lab_key = (lab_type, lab_id)
                        if lab_key in notified_labs: continue

                        try:
                            recipient_user = None
                            lab_display_name = "Unknown Lab"
                            message_detail = f"New lab test request from Dr. {doctor.name}. Patient: {patient.get_full_name()}. Test: {test_name}"
                            
                            if lab_type == 'internal':
                                lab = Lab.objects.get(id=lab_id)
                                lab_display_name = lab.name
                                # Notify clinic admins/staff associated with the internal lab's clinic
                                # Assuming Staff model has clinic fk and is_admin/appropriate role field
                                clinic_recipients = User.objects.filter(staff__clinic=doctor.clinic, staff__is_admin=True) # Adjust query as needed
                                if not clinic_recipients.exists():
                                    logger.warning(f"No admin staff found for clinic {doctor.clinic.id} to notify about internal lab test request for lab {lab_display_name} ({lab_id}).")
                                else:
                                    for recipient in clinic_recipients:
                                        create_notification(
                                            recipient=recipient,
                                            message=f"{message_detail} for your internal lab {lab_display_name}.",
                                            sender=request.user,
                                            notification_type='lab_test_new',
                                            related_object=lab_prescription
                                        )
                                    notified_labs.add(lab_key)

                            elif lab_type == 'external':
                                lab_profile = LabProfile.objects.select_related('user').get(id=lab_id)
                                lab_display_name = lab_profile.name
                                if lab_profile.user:
                                    create_notification(
                                        recipient=lab_profile.user,
                                        message=f"{message_detail} for your lab {lab_display_name} (from Clinic: {doctor.clinic.name}).",
                                        sender=request.user,
                                        notification_type='lab_test_new',
                                        related_object=lab_prescription
                                    )
                                    notified_labs.add(lab_key)
                                else:
                                    logger.warning(f"External LabProfile {lab_profile.id} ({lab_display_name}) has no associated user to notify.")

                        except (Lab.DoesNotExist, LabProfile.DoesNotExist):
                            logger.error(f"Notification Error: Could not find lab - Type={lab_type}, ID={lab_id}")
                        except Exception as e:
                            logger.error(f"Notification Error: Error processing lab {lab_key}: {e}")
                            
                except Exception as e:
                    logger.error(f"General error during lab notification processing: {e}")
                    messages.warning(request, "Prescription created, but failed to send some lab notifications.")
            # --- End Notifications ---
            
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

    # Get available labs
    internal_labs = Lab.objects.filter(clinic=doctor.clinic)
    external_labs = LabProfile.objects.filter(is_approved=True)

    context = {
        'patient': patient,
        'doctor': doctor,
        'vitals': latest_vitals,
        'has_lab': internal_labs.exists() or external_labs.exists(),
        'internal_labs': internal_labs,
        'external_labs': external_labs
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
            lab_tests.extend(LabTest.objects.filter(prescription=lab_prescription))
        
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

