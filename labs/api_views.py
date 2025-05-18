from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsLabOwnerOrStaff
from .serializers import LabResultUploadSerializer
import hashlib
from rest_framework import viewsets, generics
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from .models import (
    LabProfile, 
    TestDefinition, 
    LabOrder, 
    LabOrderTest, 
    LabResult,
    ExternalLabTestOffering
)
from .serializers import (
    LabProfileSerializer,
    TestDefinitionSerializer,
    LabOrderSerializer,
    LabOrderTestSerializer,
    LabResultSerializer,
    ExternalLabTestOfferingSerializer
)
from users.models import Patient, Doctor
import json
from django.utils import timezone

class LabResultUploadView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsLabOwnerOrStaff]
    
    def post(self, request, *args, **kwargs):
        serializer = LabResultUploadSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                result = serializer.save()
                
                # Calculate file hash
                result_file = result.result_file
                sha256_hash = hashlib.sha256()
                for chunk in result_file.chunks():
                    sha256_hash.update(chunk)
                result.file_hash = sha256_hash.hexdigest()
                result.save()
                
                return Response({
                    'status': 'success',
                    'message': 'Result uploaded successfully',
                    'result_id': result.id
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LabProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing and retrieving lab profiles
    """
    queryset = LabProfile.objects.filter(is_approved=True)
    serializer_class = LabProfileSerializer
    permission_classes = [IsAuthenticated]

class TestDefinitionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing and retrieving test definitions
    """
    queryset = TestDefinition.objects.all()
    serializer_class = TestDefinitionSerializer
    permission_classes = [IsAuthenticated]

class PatientLabOrdersView(generics.ListAPIView):
    """
    API endpoint for listing patient's lab orders
    """
    serializer_class = LabOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        patient = get_object_or_404(Patient, user=self.request.user)
        return LabOrder.objects.filter(patient=patient).order_by('-order_date')

class LabOrderDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving lab order details
    """
    serializer_class = LabOrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = LabOrder.objects.all()

    def get_object(self):
        lab_order = get_object_or_404(LabOrder, pk=self.kwargs['pk'])
        # Check if user is authorized to view this lab order
        if self.request.user.is_staff or lab_order.patient.user == self.request.user:
            return lab_order
        # Check if user is the doctor who recommended the lab order
        if lab_order.doctor and lab_order.doctor.user == self.request.user:
            return lab_order
        # Check if user is staff of the chosen lab
        if lab_order.chosen_lab and hasattr(self.request.user, 'lab_profile'):
            if self.request.user.lab_profile == lab_order.chosen_lab:
                return lab_order
        return Response({"detail": "Not authorized to view this lab order."}, 
                       status=status.HTTP_403_FORBIDDEN)

class LabResultDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving lab result details
    """
    serializer_class = LabResultSerializer
    permission_classes = [IsAuthenticated]
    queryset = LabResult.objects.all()

    def get_object(self):
        lab_result = get_object_or_404(LabResult, pk=self.kwargs['pk'])
        lab_order = lab_result.order
        
        # Check if user is authorized to view this lab result
        if self.request.user.is_staff:
            return lab_result
        if lab_order.patient.user == self.request.user:
            return lab_result
        if lab_order.doctor and lab_order.doctor.user == self.request.user:
            return lab_result
        if lab_order.chosen_lab and hasattr(self.request.user, 'lab_profile'):
            if self.request.user.lab_profile == lab_order.chosen_lab:
                return lab_result
        
        return Response({"detail": "Not authorized to view this lab result."}, 
                       status=status.HTTP_403_FORBIDDEN)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_lab_test(request):
    """
    Book a lab test
    """
    # Extract data from request
    tests = request.data.get('tests', [])
    doctor_id = request.data.get('doctor_id')
    
    # Validate request data
    if not tests:
        return Response({
            'error': 'At least one test must be specified'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get patient
    patient = get_object_or_404(Patient, user=request.user)
    
    # Get doctor if provided
    doctor = None
    if doctor_id:
        doctor = get_object_or_404(Doctor, id=doctor_id)
    
    # Create lab order
    lab_order = LabOrder.objects.create(
        patient=patient,
        doctor=doctor,
        status='PENDING_PATIENT_CHOICE',
        payment_status='UNPAID'
    )
    
    # Add tests to lab order
    total_price = 0
    for test_id in tests:
        test = get_object_or_404(TestDefinition, id=test_id)
        lab_order.tests.add(test)
        
        # Create lab order test with default price
        # In a real app, we would get the price from lab offerings
        lab_order_test = LabOrderTest.objects.create(
            order=lab_order,
            test=test,
            price=0,  # Will be updated when lab is chosen
            status='PENDING'
        )
    
    return Response({
        'success': True,
        'message': 'Lab test booked successfully',
        'lab_order': LabOrderSerializer(lab_order).data
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def choose_lab_for_order(request, lab_order_id):
    """
    Choose a lab for an existing lab order
    """
    # Extract data from request
    lab_profile_id = request.data.get('lab_profile_id')
    
    # Validate request data
    if not lab_profile_id:
        return Response({
            'error': 'Lab profile ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get lab order and verify access
    lab_order = get_object_or_404(LabOrder, id=lab_order_id)
    if lab_order.patient.user != request.user:
        return Response({
            'error': 'Not authorized to update this lab order'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if lab order is in a valid state
    if lab_order.status != 'PENDING_PATIENT_CHOICE':
        return Response({
            'error': f'Cannot choose lab for order with status "{lab_order.status}"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get lab profile
    lab_profile = get_object_or_404(LabProfile, id=lab_profile_id, is_approved=True)
    
    # Update lab order
    lab_order.chosen_lab = lab_profile
    lab_order.status = 'PENDING_PAYMENT'
    
    # Update test prices based on lab's offerings
    total_price = 0
    for order_test in lab_order.order_tests.all():
        # Try to get the lab's price for this test
        try:
            offering = ExternalLabTestOffering.objects.get(
                lab_profile=lab_profile,
                test=order_test.test,
                is_active=True
            )
            order_test.price = offering.price
            order_test.save()
            total_price += offering.price
        except ExternalLabTestOffering.DoesNotExist:
            # If no specific offering, use a default price
            # In a real app, we might want to handle this differently
            default_price = 500  # Default price in currency units
            order_test.price = default_price
            order_test.save()
            total_price += default_price
    
    # Update total price
    lab_order.total_price = total_price
    lab_order.save()
    
    return Response({
        'success': True,
        'message': 'Lab chosen successfully',
        'lab_order': LabOrderSerializer(lab_order).data
    })

# Staff API views

class StaffDashboardView(APIView):
    """
    API endpoint for lab staff dashboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            lab_profile = request.user.lab_profile
        except:
            return Response({
                'error': 'User is not lab staff'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get pending lab orders
        pending_orders_count = LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status__in=['PENDING_PAYMENT', 'PENDING_LAB']
        ).count()
        
        # Get processing lab orders
        processing_orders_count = LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status='PROCESSING'
        ).count()
        
        # Get completed lab orders
        completed_orders_count = LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status__in=['RESULT_UPLOADED', 'COMPLETED']
        ).count()
        
        # Count today's orders
        today = timezone.now().date()
        today_orders_count = LabOrder.objects.filter(
            chosen_lab=lab_profile,
            order_date__date=today
        ).count()
        
        return Response({
            'lab_name': lab_profile.name,
            'staff_name': request.user.get_full_name(),
            'pending_orders': pending_orders_count,
            'processing_orders': processing_orders_count,
            'completed_orders': completed_orders_count,
            'today_orders': today_orders_count
        })

class PendingLabOrdersView(generics.ListAPIView):
    """
    API endpoint for listing pending lab orders for a lab
    """
    serializer_class = LabOrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        try:
            lab_profile = self.request.user.lab_profile
        except:
            return LabOrder.objects.none()
        
        return LabOrder.objects.filter(
            chosen_lab=lab_profile,
            status__in=['PENDING_PAYMENT', 'PENDING_LAB', 'PROCESSING']
        ).order_by('-order_date')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_lab_order_status(request, lab_order_id):
    """
    Update lab order status (for lab staff)
    """
    # Check if user is lab staff
    try:
        lab_profile = request.user.lab_profile
    except:
        return Response({
            'error': 'User is not lab staff'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get the lab order
    lab_order = get_object_or_404(LabOrder, id=lab_order_id)
    
    # Check if this lab is authorized to update this order
    if lab_order.chosen_lab != lab_profile:
        return Response({
            'error': 'Not authorized to update this lab order'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get new status
    new_status = request.data.get('status')
    
    # Check if status is valid
    valid_statuses = ['PENDING_LAB', 'PROCESSING', 'COMPLETED', 'CANCELLED']
    if not new_status or new_status not in valid_statuses:
        return Response({
            'error': f'Invalid status. Valid statuses are: {", ".join(valid_statuses)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update lab order status
    lab_order.status = new_status
    lab_order.save()
    
    return Response({
        'success': True,
        'message': f'Lab order status updated to {new_status}',
        'lab_order': LabOrderSerializer(lab_order).data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def upload_lab_result(request, lab_order_id):
    """
    Upload lab result (for lab staff)
    """
    # Check if user is lab staff
    try:
        lab_profile = request.user.lab_profile
    except:
        return Response({
            'error': 'User is not lab staff'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get the lab order
    lab_order = get_object_or_404(LabOrder, id=lab_order_id)
    
    # Check if this lab is authorized to update this order
    if lab_order.chosen_lab != lab_profile:
        return Response({
            'error': 'Not authorized to upload results for this lab order'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if lab order is in a valid state
    if lab_order.status not in ['PROCESSING', 'RESULT_UPLOADED']:
        return Response({
            'error': f'Cannot upload results for order with status "{lab_order.status}"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Process result upload
    serializer = LabResultUploadSerializer(data=request.data)
    if serializer.is_valid():
        result_file = serializer.validated_data.get('result_file')
        structured_result = serializer.validated_data.get('structured_result')
        lab_metadata = serializer.validated_data.get('lab_metadata')
        
        # Check if this order already has a result
        if hasattr(lab_order, 'result'):
            # Update existing result
            lab_result = lab_order.result
            if result_file:
                lab_result.result_file = result_file
            if structured_result:
                lab_result.structured_result = structured_result
            if lab_metadata:
                lab_result.lab_metadata = lab_metadata
            lab_result.uploaded_at = timezone.now()
            lab_result.uploaded_by_lab = lab_profile
            lab_result.uploaded_by_user = request.user
            lab_result.save()
        else:
            # Create new result
            lab_result = LabResult.objects.create(
                order=lab_order,
                result_file=result_file,
                structured_result=structured_result,
                lab_metadata=lab_metadata,
                uploaded_by_lab=lab_profile,
                uploaded_by_user=request.user
            )
        
        # Update lab order status
        lab_order.status = 'RESULT_UPLOADED'
        lab_order.save()
        
        return Response({
            'success': True,
            'message': 'Lab result uploaded successfully',
            'lab_result': LabResultSerializer(lab_result).data
        })
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 