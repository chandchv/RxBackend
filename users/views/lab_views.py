from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import LabTest, LabTechnician, Lab
from ..serializers import LabTestSerializer, LabTechnicianSerializer

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
    """View for lab technicians to view and update test details"""
    try:
        if not hasattr(request.user, 'labtechnician'):
            messages.error(request, 'Access denied. Lab technician privileges required.')
            return redirect('users:dashboard')

        test = get_object_or_404(
            LabTest.objects.select_related(
                'patient',
                'doctor',
                'lab',
                'technician'
            ),
            id=pk,
            lab__clinic=request.user.labtechnician.clinic
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
            
            elif action == 'assign_technician':
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
        }
        
        return render(request, 'lab/lab_test_detail.html', context)

    except Exception as e:
        print(f"Error in lab test detail: {str(e)}")
        messages.error(request, f'Error accessing test details: {str(e)}')
        return redirect('users:lab_dashboard')

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