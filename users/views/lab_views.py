from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import LabTest, LabTechnician, Lab
from labs.models import TestDefinition, LabProfile
from ..serializers import LabTestSerializer, LabTechnicianSerializer
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.shortcuts import redirect

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
            if new_status in dict(LabTest.TEST_STATUS):
                old_status = test.status
                test.status = new_status
                
                # Handle file uploads for completed tests
                if new_status == 'COMPLETED' and request.FILES.get('result_file'):
                    test.result_file = request.FILES.get('result_file')
                
                # Save the test with its new status
                test.save()
                
                # Update prescription status if all tests are completed
                if new_status == 'COMPLETED':
                    prescription = test.prescription
                    all_tests = LabTest.objects.filter(prescription=prescription)
                    if all(t.status == 'COMPLETED' for t in all_tests):
                        prescription.status = 'COMPLETED'
                        prescription.save()
                
                messages.success(request, f'Test status updated from {old_status} to {new_status}')
                
                # Create notification for patient
                try:
                    from notifications.utils import create_notification
                    patient_user = test.prescription.patient.user
                    
                    # Get the doctor user
                    doctor_user = test.prescription.doctor
                    
                    # Create message with more details for COMPLETED status
                    if new_status == 'COMPLETED':
                        test_name = test.test_definition.name if test.test_definition else 'Unknown Test'
                        base_message = f"Lab test '{test_name}' has been completed and results are available."
                        
                        # Include direct links to the dashboards, not specific test pages
                        # This ensures users see the notification on their main dashboard
                        patient_link = "/users/patient/dashboard/"
                        doctor_link = "/users/doctor/dashboard/"
                    else:
                        base_message = f"Your lab test for {test.test_definition.name if test.test_definition else 'Unknown Test'} has been updated to {new_status}"
                        patient_link = None
                        doctor_link = None
                    
                    # Notify patient
                    if patient_user:
                        patient_message = f"Your {base_message} Please check your dashboard to review."
                        create_notification(
                            recipient=patient_user,
                            message=patient_message,
                            sender=request.user,
                            notification_type='lab_test_update',
                            related_object=test,
                            action_url=patient_link
                        )
                    
                    # Notify doctor for completed tests - always send for COMPLETED status
                    if new_status == 'COMPLETED' and doctor_user:
                        doctor_message = f"Lab test '{test_name}' for patient {test.prescription.patient.get_full_name()} has been completed and requires your review. Check your dashboard."
                        create_notification(
                            recipient=doctor_user,
                            message=doctor_message,
                            sender=request.user,
                            notification_type='lab_test_completed',
                            related_object=test,
                            action_url=doctor_link
                        )
                except Exception as e:
                    # Log but don't fail if notification creation fails
                    print(f"Error sending notification: {e}")
                
            else:
                messages.error(request, f'Invalid status: {new_status}')
            
            # Return to the lab test detail page
            return redirect('users:lab_test_detail', pk=test.id)
        
        # If GET request, show the form
        context = {
            'test': test,
            'status_choices': LabTest.TEST_STATUS,
            'current_status': test.status,
        }
        
        return render(request, 'lab/update_lab_test_status.html', context)
    
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
            
        # Get the lab test and verify patient's access
        test = get_object_or_404(
            LabTest.objects.select_related(
                'prescription',
                'prescription__patient',
                'prescription__doctor',
                'test_definition'
            ),
            id=pk
        )
        
        # Verify the requesting patient is associated with the test
        if test.prescription.patient.user != request.user:
            messages.error(request, 'You do not have permission to view this test.')
            return redirect('users:patient_dashboard')
            
        context = {
            'test': test,
            'prescription': test.prescription,
            'doctor': test.prescription.doctor
        }
        
        return render(request, 'patient/lab_test_detail.html', context)
        
    except Exception as e:
        print(f"Error in patient lab test detail: {str(e)}")
        messages.error(request, f'Error accessing test details: {str(e)}')
        return redirect('users:patient_dashboard') 