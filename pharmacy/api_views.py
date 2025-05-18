from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Pharmacy, Prescription, PrescriptionDrug, PharmacyStock, PharmacyStaff
from .serializers import (
    PharmacySerializer, 
    PrescriptionSerializer, 
    PrescriptionDrugSerializer,
    PharmacyStockSerializer
)
from users.models import Patient

class PharmacyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing and retrieving pharmacies
    """
    queryset = Pharmacy.objects.filter(is_active=True)
    serializer_class = PharmacySerializer
    permission_classes = [IsAuthenticated]

class PatientPrescriptionsView(generics.ListAPIView):
    """
    API endpoint for listing patient's prescriptions
    """
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        patient = get_object_or_404(Patient, user=self.request.user)
        return Prescription.objects.filter(patient=patient).order_by('-created_at')

class PrescriptionDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving prescription details
    """
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]
    queryset = Prescription.objects.all()

    def get_object(self):
        prescription = get_object_or_404(Prescription, pk=self.kwargs['pk'])
        # Check if user is authorized to view this prescription
        if self.request.user.is_staff or prescription.patient.user == self.request.user:
            return prescription
        # PharmacyStaff can view prescriptions too
        try:
            staff = PharmacyStaff.objects.get(user=self.request.user)
            return prescription
        except PharmacyStaff.DoesNotExist:
            pass
        return Response({"detail": "Not authorized to view this prescription."}, 
                       status=status.HTTP_403_FORBIDDEN)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_medicine_availability(request, pharmacy_id, medicine_id):
    """
    Check if a medicine is available at a specific pharmacy
    """
    try:
        pharmacy_stock = PharmacyStock.objects.get(
            pharmacy_id=pharmacy_id, 
            medicine_id=medicine_id
        )
        
        return Response({
            'available': pharmacy_stock.quantity > 0,
            'quantity': pharmacy_stock.quantity,
            'expiry_date': pharmacy_stock.expiry_date,
            'unit_price': pharmacy_stock.unit_price
        })
    except PharmacyStock.DoesNotExist:
        return Response({
            'available': False,
            'quantity': 0
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_medication_delivery(request):
    """
    Request medication delivery from a pharmacy
    """
    # Extract data from request
    prescription_id = request.data.get('prescription_id')
    pharmacy_id = request.data.get('pharmacy_id')
    delivery_details = request.data.get('delivery_details', {})
    
    # Validate request data
    if not prescription_id or not pharmacy_id:
        return Response({
            'error': 'Prescription ID and pharmacy ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get the prescription and check authorization
    prescription = get_object_or_404(Prescription, pk=prescription_id)
    if prescription.patient.user != request.user:
        return Response({
            'error': 'You are not authorized to request delivery for this prescription'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get the pharmacy
    pharmacy = get_object_or_404(Pharmacy, pk=pharmacy_id, is_active=True)
    
    # Check if prescription is in a valid state for delivery
    if prescription.status not in ['new', 'processing']:
        return Response({
            'error': f'Cannot request delivery for prescription with status "{prescription.status}"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update prescription status
    prescription.status = 'processing'
    prescription.save()
    
    # In a real system, we would create a delivery record and 
    # potentially send notifications to the pharmacy, but for now
    # we'll just return a success response
    
    return Response({
        'success': True,
        'message': 'Delivery request submitted successfully',
        'prescription_id': prescription_id,
        'pharmacy': {
            'id': pharmacy.id,
            'name': pharmacy.name,
            'address': pharmacy.address,
            'phone': pharmacy.phone,
            'email': pharmacy.email
        },
        'delivery_details': delivery_details
    }, status=status.HTTP_201_CREATED)

# Staff API views

class StaffDashboardView(APIView):
    """
    API endpoint for pharmacy staff dashboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            staff = PharmacyStaff.objects.get(user=request.user)
        except PharmacyStaff.DoesNotExist:
            return Response({
                'error': 'User is not pharmacy staff'
            }, status=status.HTTP_403_FORBIDDEN)
        
        pharmacy = staff.pharmacy
        
        # Get pending prescriptions
        pending_prescriptions_count = Prescription.objects.filter(
            status__in=['new', 'processing']
        ).count()
        
        # Get low stock items
        low_stock_items = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            quantity__lte=models.F('min_stock_level')
        ).count()
        
        # Get expired stock items
        from django.utils import timezone
        expired_stock_items = PharmacyStock.objects.filter(
            pharmacy=pharmacy,
            expiry_date__lt=timezone.now().date()
        ).count()
        
        return Response({
            'pharmacy_name': pharmacy.name,
            'staff_name': request.user.get_full_name(),
            'staff_role': staff.get_role_display(),
            'pending_prescriptions': pending_prescriptions_count,
            'low_stock_items': low_stock_items,
            'expired_stock_items': expired_stock_items
        })

class StaffInventoryView(generics.ListAPIView):
    """
    API endpoint for pharmacy inventory
    """
    serializer_class = PharmacyStockSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        try:
            staff = PharmacyStaff.objects.get(user=self.request.user)
        except PharmacyStaff.DoesNotExist:
            return PharmacyStock.objects.none()
        
        return PharmacyStock.objects.filter(pharmacy=staff.pharmacy)

class PendingPrescriptionsView(generics.ListAPIView):
    """
    API endpoint for listing pending prescriptions for a pharmacy
    """
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        try:
            staff = PharmacyStaff.objects.get(user=self.request.user)
        except PharmacyStaff.DoesNotExist:
            return Prescription.objects.none()
        
        return Prescription.objects.filter(
            status__in=['new', 'processing', 'partially_dispensed']
        ).order_by('-created_at')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_prescription(request, prescription_id):
    """
    Process a prescription (for pharmacy staff)
    """
    # Check if user is pharmacy staff
    try:
        staff = PharmacyStaff.objects.get(user=request.user)
    except PharmacyStaff.DoesNotExist:
        return Response({
            'error': 'User is not pharmacy staff'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get the prescription
    prescription = get_object_or_404(Prescription, pk=prescription_id)
    
    # Check if prescription is in a valid state for processing
    if prescription.status in ['cancelled', 'expired', 'fully_dispensed']:
        return Response({
            'error': f'Cannot process prescription with status "{prescription.status}"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Process the prescription according to the action
    action = request.data.get('action', '')
    
    if action == 'dispense':
        # Get the dispensed drugs
        dispensed_drugs = request.data.get('dispensed_drugs', [])
        
        # Validate dispensed drugs
        if not dispensed_drugs:
            return Response({
                'error': 'No drugs dispensed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process each dispensed drug
        for drug_data in dispensed_drugs:
            prescription_drug_id = drug_data.get('prescription_drug_id')
            quantity = drug_data.get('quantity', 0)
            
            if not prescription_drug_id or quantity <= 0:
                continue
            
            # Get the prescription drug
            prescription_drug = get_object_or_404(PrescriptionDrug, pk=prescription_drug_id)
            
            # Create a dispensing record
            from .models import Dispensing
            Dispensing.objects.create(
                prescription_drug=prescription_drug,
                pharmacy=staff.pharmacy,
                quantity=quantity,
                batch_number_dispensed=drug_data.get('batch_number', ''),
                dispensed_price_per_unit=drug_data.get('price_per_unit', 0),
                total_dispensed_price=drug_data.get('total_price', 0),
                dispensed_by=request.user,
                notes=drug_data.get('notes', '')
            )
            
            # Update pharmacy stock
            try:
                stock = PharmacyStock.objects.get(
                    pharmacy=staff.pharmacy,
                    medicine=prescription_drug.drug
                )
                
                if stock.quantity >= quantity:
                    stock.quantity -= quantity
                    stock.save()
            except PharmacyStock.DoesNotExist:
                pass
        
        # Update the prescription status
        prescription.update_status()
        
        return Response({
            'success': True,
            'message': 'Prescription processed successfully',
            'prescription': PrescriptionSerializer(prescription).data
        })
    
    elif action == 'cancel':
        # Update prescription status
        prescription.status = 'cancelled'
        prescription.save()
        
        return Response({
            'success': True,
            'message': 'Prescription cancelled',
            'prescription': PrescriptionSerializer(prescription).data
        })
    
    else:
        return Response({
            'error': 'Invalid action. Valid actions are: dispense, cancel'
        }, status=status.HTTP_400_BAD_REQUEST) 