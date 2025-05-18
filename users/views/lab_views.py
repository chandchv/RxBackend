from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import LabTest, LabTechnician, Lab, LabTestPrescription
from labs.models import TestDefinition, LabProfile
from ..serializers import LabTestSerializer, LabTechnicianSerializer
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q
from django.core.paginator import Paginator
from notifications.models import Notification
from django.core.files.storage import default_storage
import os
from notifications.utils import create_notification
import logging

logger = logging.getLogger(__name__)

@login_required
def doctor_lab_tests(request):
    """View for doctors to see all lab tests they've prescribed"""
    try:
        # Check if user has doctor profile
        if not hasattr(request.user, 'doctor'):
            messages.error(request, 'Access denied. Doctor privileges required.')
            return redirect('users:dashboard')

        doctor = request.user.doctor
        
        # Get search parameters
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        
        # Base query - get all lab tests prescribed by this doctor
        lab_tests = LabTest.objects.filter(
            prescription__doctor=request.user
        ).select_related(
            'prescription__patient',
            'test_definition'
        ).order_by('-created_at')
        
        # Apply filters
        if search_query:
            lab_tests = lab_tests.filter(
                Q(prescription__patient__first_name__icontains=search_query) |
                Q(prescription__patient__last_name__icontains=search_query) |
                Q(test_definition__name__icontains=search_query)
            )
            
        if status_filter:
            lab_tests = lab_tests.filter(status=status_filter)
            
        # Paginate results
        paginator = Paginator(lab_tests, 10)  # Show 10 tests per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'lab_tests': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'status_choices': LabTest.TEST_STATUS,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj,
            'paginator': paginator,
        }
        
        return render(request, 'doctor/lab_tests.html', context)
        
    except Exception as e:
        print(f"Error in doctor lab tests: {str(e)}")
        messages.error(request, f'Error accessing lab tests: {str(e)}')
        return redirect('users:doctor_dashboard')

@login_required
def lab_dashboard(request):
    """View for lab technicians to manage lab tests"""
    try:
        if not hasattr(request.user, 'labtechnician'):
            messages.error(request, 'Access denied. Lab technician privileges required.')
            return redirect('users:dashboard')

        technician = request.user.labtechnician
        today = timezone.now().date()

        # Get lab tests for the technician's clinic
        lab_tests = LabTest.objects.filter(
            lab__clinic=technician.clinic
        ).select_related(
            'patient',
            'doctor',
            'lab'
        ).order_by('-created_at')

        # Get statistics
        pending_tests_count = lab_tests.filter(status='REQUESTED').count()
        today_tests_count = lab_tests.filter(created_at__date=today).count()
        processing_tests_count = lab_tests.filter(status='PROCESSING').count()
        completed_today_count = lab_tests.filter(
            status='COMPLETED',
            updated_at__date=today
        ).count()

        context = {
            'lab_tests': lab_tests,
            'pending_tests_count': pending_tests_count,
            'today_tests_count': today_tests_count,
            'processing_tests_count': processing_tests_count,
            'completed_today_count': completed_today_count,
        }

        return render(request, 'lab/lab_dashboard.html', context)

    except Exception as e:
        print(f"Error in lab dashboard: {str(e)}")
        messages.error(request, f'Error accessing lab dashboard: {str(e)}')
        return redirect('users:dashboard')

@login_required
def lab_test_detail(request, pk):
    """View for lab users to view and update test details"""
    try:
        # Determine whether this is a lab technician (internal) or LabProfile user (external)
        is_lab_technician = hasattr(request.user, 'labtechnician')
        is_lab_profile_user = LabProfile.objects.filter(user=request.user).exists()
        
        if not (is_lab_technician or is_lab_profile_user):
            messages.error(request, 'Access denied. Lab privileges required.')
            return redirect('users:dashboard')

        # Get the test using the appropriate filter based on user type
        if is_lab_technician:
            # For internal lab users
            test = get_object_or_404(
                LabTest.objects.select_related(
                    'prescription',
                    'prescription__patient',
                    'prescription__doctor',
                    'test_definition'
                ),
                id=pk,
                prescription__inhouse_lab__clinic=request.user.labtechnician.clinic
            )
        else:
            # For external lab users
            lab_profile = get_object_or_404(LabProfile, user=request.user)
            test = get_object_or_404(
                LabTest.objects.select_related(
                    'prescription',
                    'prescription__patient',
                    'prescription__doctor',
                    'test_definition'
                ),
                id=pk,
                prescription__external_lab=lab_profile
            )

        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'update_status':
                new_status = request.POST.get('status')
                if new_status in dict(LabTest.TEST_STATUS):
                    test.status = new_status
                    if new_status == 'COMPLETED':
                        test.result_file = request.FILES.get('result_file')
                    test.save()
                    messages.success(request, 'Test status updated successfully')
                else:
                    messages.error(request, 'Invalid status')
            
            elif action == 'assign_technician' and is_lab_technician:
                if not test.technician:
                    test.technician = request.user.labtechnician
                    test.status = 'ASSIGNED'
                    test.save()
                    messages.success(request, 'Test assigned to you')
                else:
                    messages.error(request, 'Test is already assigned')

        context = {
            'test': test,
            'status_choices': LabTest.TEST_STATUS,
            'collection_choices': LabTest.COLLECTION_TYPE,
            'is_lab_technician': is_lab_technician,
            'is_lab_profile_user': is_lab_profile_user
        }
        
        return render(request, 'lab/lab_test_detail.html', context)

    except Exception as e:
        print(f"Error in lab test detail: {str(e)}")
        messages.error(request, f'Error accessing test details: {str(e)}')
        return redirect('labs:doctor_requests')

class LabTestViewSet(viewsets.ModelViewSet):
    serializer_class = LabTestSerializer
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'doctor'):
            return LabTest.objects.filter(doctor=user.doctor)
        elif hasattr(user, 'patient'):
            return LabTest.objects.filter(patient=user.patient)
        elif hasattr(user, 'labtechnician'):
            return LabTest.objects.filter(technician=user.labtechnician)
        return LabTest.objects.none()

    @action(detail=True, methods=['post'])
    def assign_technician(self, request, pk=None):
        test = self.get_object()
        technician_id = request.data.get('technician_id')
        technician = get_object_or_404(LabTechnician, id=technician_id)
        
        test.technician = technician
        test.status = 'ASSIGNED'
        test.save()
        
        return Response({'status': 'Technician assigned'})

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        test = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(LabTest.TEST_STATUS):
            test.status = new_status
            test.save()
            return Response({'status': 'Test status updated'})
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def upload_result(self, request, pk=None):
        test = self.get_object()
        result_file = request.FILES.get('result_file')
        if result_file:
            test.result_file = result_file
            test.status = 'COMPLETED'
            test.save()
            return Response({'status': 'Result uploaded'})
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

@login_required
@require_GET
def get_available_labs(request):
    """API endpoint to get available labs with their test offerings"""
    try:
        # Get all active labs
        labs = Lab.objects.filter(is_active=True)
        
        # Get all available test definitions
        test_definitions = TestDefinition.objects.all()
        
        # Format the response
        labs_data = []
        for lab in labs:
            lab_data = {
                'id': lab.id,
                'name': lab.name,
                'type': lab.type,
                'available_tests': list(lab.test_definitions.values_list('name', flat=True))
            }
            labs_data.append(lab_data)
        
        return JsonResponse({
            'labs': labs_data,
            'all_tests': list(test_definitions.values_list('name', flat=True))
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def update_lab_test_status(request, test_id):
    """View for lab users to update the status of a lab test"""
    try:
        # Check if the user has a lab profile
        lab_profile = None
        
        # Handle both cases - user is associated with an internal lab or external lab profile
        if hasattr(request.user, 'labtechnician'):
            # For internal lab users
            test = get_object_or_404(
                LabTest,
                id=test_id,
                prescription__inhouse_lab__clinic=request.user.labtechnician.clinic
            )
        else:
            # For external lab users
            lab_profile = get_object_or_404(LabProfile, user=request.user)
            test = get_object_or_404(
                LabTest,
                id=test_id,
                prescription__external_lab=lab_profile
            )
        
        if request.method == 'POST':
            new_status = request.POST.get('status')
            
            # Validate status transition
            valid_transitions = {
                'REQUESTED': ['ASSIGNED'],
                'ASSIGNED': ['SAMPLE_COLLECTED'],
                'SAMPLE_COLLECTED': ['PROCESSING'],
                'PROCESSING': ['COMPLETED'],
                'COMPLETED': ['REVIEWED']  # Only doctors can mark as reviewed
            }
            
            if new_status not in valid_transitions.get(test.status, []):
                messages.error(request, f'Invalid status transition from {test.status} to {new_status}')
                return redirect('users:lab_test_detail', pk=test.id)
            
            # Update test status and related fields
            test.status = new_status
            
            # Handle status-specific updates
            if new_status == 'ASSIGNED':
                test.assigned_technician = request.POST.get('assigned_technician')
                test.expected_collection_date = request.POST.get('collection_date')
                
                # Notify patient
                patient_message = f"Your lab test has been assigned. Expected collection date: {test.expected_collection_date}"
                patient_link = f"/patient/lab-test/{test.id}"
                
                # Create notifications
                try:
                    # Notify patient
                    create_notification(
                        recipient=test.prescription.patient.user,
                        message=patient_message,
                        sender=request.user,
                        notification_type='lab_test_status_update',
                        related_object=test,
                        action_url=patient_link
                    )
                    
                    # Notify doctor
                    doctor_user = test.prescription.doctor.user
                    if doctor_user:
                        create_notification(
                            recipient=doctor_user,
                            message=f"Lab test status updated: {patient_message}",
                            sender=request.user,
                            notification_type='lab_test_status_update',
                            related_object=test,
                            action_url=f"/doctor/lab-test/{test.id}/detail/"
                        )
                except Exception as e:
                    logger.error(f"Error creating notifications for test {test.id}: {e}", exc_info=True)
                    messages.warning(request, "Test status updated, but failed to send notifications.")
            
            elif new_status == 'SAMPLE_COLLECTED':
                test.collection_notes = request.POST.get('collection_notes')
                test.collection_time = request.POST.get('collection_time')
                
                # Notify patient
                patient_message = "Your lab test sample has been collected and is being processed."
                Notification.objects.create(
                    recipient=test.prescription.patient.user,
                    message=patient_message,
                    notification_type='sample_collected',
                    related_object=test
                )
            
            elif new_status == 'PROCESSING':
                test.processing_notes = request.POST.get('processing_notes')
                test.expected_completion_date = request.POST.get('expected_completion_date')
                
                # Notify patient
                patient_message = f"Your lab test is being processed. Expected completion date: {test.expected_completion_date}"
                Notification.objects.create(
                    recipient=test.prescription.patient.user,
                    message=patient_message,
                    notification_type='test_processing',
                    related_object=test
                )
            
            elif new_status == 'COMPLETED':
                test.test_results = request.POST.get('test_results')
                
                # Handle result file upload
                if 'result_file' in request.FILES:
                    result_file = request.FILES['result_file']
                    file_name = f"lab_results/test_{test.id}/{result_file.name}"
                    
                    # Save the file
                    if test.result_file:
                        # Delete old file if it exists
                        default_storage.delete(test.result_file.name)
                    
                    test.result_file.save(file_name, result_file)
                
                # Notify both patient and doctor
                patient_message = "Your lab test results are ready. Please check your dashboard."
                doctor_message = f"Lab test results for patient {test.prescription.patient.get_full_name()} are ready for review."
                
                patient_link = f"/patient/lab-test/{test.id}"
                doctor_link = f"/doctor/lab-test/{test.id}"
                
                # Create notifications
                try:
                    # Notify patient
                    create_notification(
                        recipient=test.prescription.patient.user,
                        message=patient_message,
                        sender=request.user,
                        notification_type='lab_test_status_update',
                        related_object=test,
                        action_url=patient_link
                    )
                    
                    # Notify doctor
                    doctor_user = test.prescription.doctor.user
                    if doctor_user:
                        create_notification(
                            recipient=doctor_user,
                            message=doctor_message,
                            sender=request.user,
                            notification_type='lab_test_status_update',
                            related_object=test,
                            action_url=doctor_link
                        )
                except Exception as e:
                    logger.error(f"Error creating notifications for test {test.id}: {e}", exc_info=True)
                    messages.warning(request, "Test status updated, but failed to send notifications.")
            
            # Save all changes
            test.save()
            
            messages.success(request, f'Test status updated to {new_status}')
            return redirect('users:lab_test_detail', pk=test.id)
        
        # If GET request, show the form
        context = {
            'test': test,
            'current_status': test.status,
        }
        
        return render(request, 'labs/update_lab_test_status.html', context)
    
    except Exception as e:
        print(f"Error updating lab test status: {str(e)}")
        messages.error(request, f'Error updating test status: {str(e)}')
        return redirect('labs:doctor_requests')

@login_required
def doctor_lab_test_detail(request, pk):
    """View for doctors to review lab test details and mark as reviewed"""
    try:
        # Ensure the user is a doctor
        if not hasattr(request.user, 'doctor'):
            messages.error(request, 'Access denied. Doctor privileges required.')
            return redirect('users:dashboard')
            
        # Get the lab test and verify doctor's access
        test = get_object_or_404(
            LabTest.objects.select_related(
                'prescription',
                'prescription__patient',
                'prescription__doctor',
                'test_definition'
            ),
            id=pk
        )
        
        # Verify the requesting doctor is associated with the test
        if test.prescription.doctor != request.user:
            messages.error(request, 'You do not have permission to view this test.')
            return redirect('users:doctor_dashboard')
        
        # Handle form submission
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'mark_as_reviewed':
                # Update the status to REVIEWED if it was COMPLETED
                if test.status == 'COMPLETED':
                    old_status = test.status
                    test.status = 'REVIEWED'
                    test.save()
                    messages.success(request, 'Test has been marked as reviewed')
                    
                    # Notify patient that doctor has reviewed the test
                    try:
                        from notifications.utils import create_notification
                        patient_user = test.prescription.patient.user
                        if patient_user:
                            test_name = test.test_definition.name if test.test_definition else 'Unknown Test'
                            create_notification(
                                recipient=patient_user,
                                message=f"Dr. {request.user.get_full_name()} has reviewed your lab test: {test_name}",
                                sender=request.user,
                                notification_type='lab_test_reviewed',
                                related_object=test,
                                action_url=f"/users/lab-tests/{test.id}/detail/"
                            )
                    except Exception as e:
                        print(f"Error sending notification: {e}")
            
            elif action in ['review_and_save', 'update_analysis']:
                # Save doctor's analysis
                doctor_analysis = request.POST.get('doctor_analysis', '')
                test.doctor_analysis = doctor_analysis
                
                # If review_and_save is selected, also mark as reviewed
                if action == 'review_and_save' and test.status == 'COMPLETED':
                    test.status = 'REVIEWED'
                    status_message = 'Test has been marked as reviewed and analysis saved'
                else:
                    status_message = 'Analysis saved successfully'
                
                test.save()
                messages.success(request, status_message)
                
                # Notify patient
                try:
                    from notifications.utils import create_notification
                    patient_user = test.prescription.patient.user
                    if patient_user:
                        test_name = test.test_definition.name if test.test_definition else 'Unknown Test'
                        notification_message = f"Dr. {request.user.get_full_name()} has added analysis to your lab test: {test_name}"
                        
                        create_notification(
                            recipient=patient_user,
                            message=notification_message,
                            sender=request.user,
                            notification_type='lab_test_analysis',
                            related_object=test,
                            action_url=f"/users/lab-tests/{test.id}/detail/"
                        )
                except Exception as e:
                    print(f"Error sending notification: {e}")
            
        # Get related prescription
        prescription = test.prescription
            
        context = {
            'test': test,
            'prescription': prescription,
            'patient': prescription.patient,
            'doctor': request.user.doctor,
        }
        
        return render(request, 'doctor/lab_test_detail.html', context)
        
    except Exception as e:
        print(f"Error in doctor lab test detail: {str(e)}")
        messages.error(request, f'Error accessing test details: {str(e)}')
        return redirect('users:doctor_dashboard')

@login_required
def patient_lab_test_detail(request, pk):
    """View for patients to review their lab test details"""
    try:
        # Ensure the user is a patient
        if not hasattr(request.user, 'patient'):
            messages.error(request, 'Access denied. Patient privileges required.')
            return redirect('users:dashboard')
        
        patient = request.user.patient
            
        # Try to get the lab test - handle both direct and through prescription patient relationship
        try:
            test = LabTest.objects.select_related(
                'prescription',
                'prescription__patient',
                'prescription__doctor',
                'test_definition'
            ).get(id=pk)
            
            # Verify the requesting patient is associated with the test
            if test.prescription and test.prescription.patient != patient:
                messages.error(request, 'You do not have permission to view this test.')
                return redirect('users:patient_dashboard')
                
        except LabTest.DoesNotExist:
            # If test doesn't exist with direct relationship, look for it in lab test prescriptions
            lab_prescriptions = LabTestPrescription.objects.filter(patient=patient)
            test = None
            
            for prescription in lab_prescriptions:
                try:
                    test = LabTest.objects.get(
                        prescription=prescription,
                        id=pk
                    )
                    if test:
                        break
                except LabTest.DoesNotExist:
                    continue
            
            if not test:
                messages.error(request, 'Lab test not found.')
                return redirect('users:patient_test_results')
            
        context = {
            'test': test,
            'prescription': test.prescription,
            'doctor': test.prescription.doctor if test.prescription else None
        }
        
        return render(request, 'patient/lab_test_detail.html', context)
        
    except Exception as e:
        print(f"Error in patient lab test detail: {str(e)}")
        messages.error(request, f'Error accessing test details: {str(e)}')
        return redirect('users:patient_dashboard') 