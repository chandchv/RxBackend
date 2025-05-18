from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from billing.services import record_invoice_payment
from .models import Bill, BillItem, InsuranceClaim, LabTestBilling, Payment, BillingItem, ConsultationBilling
from .serializers import (
    BillItemSerializer,
    ConsultationBillingSerializer,
    InsuranceClaimSerializer,
    LabTestBillingSerializer, 
    PaymentSerializer,
    BillingItemSerializer,
    BillListSerializer,
    BillDetailSerializer
)
from users.models import Patient, Doctor, Appointment
from django.utils import timezone
import uuid
from datetime import timedelta

# Custom permissions
class IsOwnerOrStaff(permissions.BasePermission):
    """
    Permission to check if the user is the owner or a staff member.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check if the user is the patient
        if hasattr(obj, 'patient') and obj.patient.user == request.user:
            return True
        
        # Check if the user is the doctor
        if hasattr(obj, 'doctor') and obj.doctor.user == request.user:
            return True
        
        return False

class IsDoctor(permissions.BasePermission):
    """
    Permission to check if the user is a doctor.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'doctor')

class IsBillingStaff(permissions.BasePermission):
    """
    Permission to check if the user is a billing staff member.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or 
            request.user.is_superuser or 
            (hasattr(request.user, 'user_profile') and request.user.user_profile.role == 'billing')
        )


class BillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for listing and retrieving bills
    """
    queryset = Bill.objects.all()
    serializer_class = BillDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Check if user is a patient
        try:
            patient = Patient.objects.get(user=user)
            return Bill.objects.filter(patient=patient).order_by('-bill_date')
        except Patient.DoesNotExist:
            pass
        
        # Check if user is a doctor
        try:
            doctor = Doctor.objects.get(user=user)
            return Bill.objects.filter(doctor=doctor).order_by('-bill_date')
        except Doctor.DoesNotExist:
            pass
        
        # For staff users, return all bills
        if user.is_staff:
            return Bill.objects.all().order_by('-bill_date')
        
        # Default case, return empty queryset
        return Bill.objects.none()


class BillItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for bill items.
    """
    queryset = BillItem.objects.all()
    serializer_class = BillItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    
    def get_queryset(self):
        """Filter bill items based on the bill"""
        bill_id = self.kwargs.get('bill_pk')
        if bill_id:
            return BillItem.objects.filter(bill_id=bill_id)
        return BillItem.objects.none()


class PaymentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for payments.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]
    
    def get_queryset(self):
        """Filter payments based on the bill"""
        bill_id = self.kwargs.get('bill_pk')
        if bill_id:
            return Payment.objects.filter(bill_id=bill_id)
        return Payment.objects.none()
    
    def perform_create(self, serializer):
        """Add the logged-in user as recorded_by when creating a payment"""
        serializer.save(recorded_by=self.request.user)


class BillingItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for billing items.
    """
    queryset = BillingItem.objects.all()
    serializer_class = BillingItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter billing items based on clinic and type"""
        queryset = BillingItem.objects.filter(is_active=True)
        
        user = self.request.user
        if hasattr(user, 'user_profile') and user.user_profile.clinic:
            queryset = queryset.filter(clinic=user.user_profile.clinic)
        elif hasattr(user, 'doctor') and user.doctor.clinic:
            queryset = queryset.filter(clinic=user.doctor.clinic)
        
        item_type = self.request.query_params.get('type')
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        
        return queryset


class LabTestBillingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for lab test billing.
    """
    queryset = LabTestBilling.objects.all()
    serializer_class = LabTestBillingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]


class ConsultationBillingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for consultation billing.
    """
    queryset = ConsultationBilling.objects.all()
    serializer_class = ConsultationBillingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    """
    API endpoint for insurance claims.
    """
    queryset = InsuranceClaim.objects.all()
    serializer_class = InsuranceClaimSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]


class PatientBillsView(generics.ListAPIView):
    """
    API endpoint for listing patient's bills
    """
    serializer_class = BillListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        patient = get_object_or_404(Patient, user=self.request.user)
        return Bill.objects.filter(patient=patient).order_by('-bill_date')


class BillDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving bill details
    """
    serializer_class = BillDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Bill.objects.all()
    
    def get_object(self):
        bill = get_object_or_404(Bill, pk=self.kwargs['pk'])
        # Check if user is authorized to view this bill
        if self.request.user.is_staff:
            return bill
        if bill.patient.user == self.request.user:
            return bill
        if bill.doctor and bill.doctor.user == self.request.user:
            return bill
        return Response({"detail": "Not authorized to view this bill."}, 
                       status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def download_bill_pdf(request, pk):
    """
    Download bill PDF
    """
    bill = get_object_or_404(Bill, pk=pk)
    
    # Check if user is authorized to download this bill PDF
    if not (request.user.is_staff or bill.patient.user == request.user or 
            (bill.doctor and bill.doctor.user == request.user)):
        return Response({"detail": "Not authorized to download this bill PDF."}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    # In a real app, we would generate a PDF here
    # For now, we'll just return a mock URL
    return Response({
        'pdf_url': f'/api/billing/bills/{bill.id}/pdf/'
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pay_bill_balance(request, pk):
    """
    Pay balance for a bill
    """
    bill = get_object_or_404(Bill, pk=pk)
    
    # Check if user is authorized to pay this bill
    if bill.patient.user != request.user:
        return Response({"detail": "Not authorized to pay this bill."}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    # Check if bill is in a valid state for payment
    if bill.status == 'cancelled':
        return Response({
            'error': 'Cannot pay a cancelled bill'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if bill.status == 'paid':
        return Response({
            'error': 'Bill is already fully paid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Extract data from request
    payment_intent_id = request.data.get('payment_intent_id')
    
    if not payment_intent_id:
        return Response({
            'error': 'Payment intent ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Process payment
    # In a real app, we would verify the payment intent with the payment gateway
    # For now, we'll just create a payment record
    payment = Payment.objects.create(
        bill=bill,
        amount=bill.due_amount,
        payment_date=timezone.now(),
        payment_method='card',  # Assuming card payment
        reference_number=payment_intent_id,
        notes='Payment made via mobile app',
        receipt_number=f'R-{uuid.uuid4().hex[:8].upper()}',
        created_by=request.user
    )
    
    # Update bill status
    bill.update_status()
    
    return Response({
        'success': True,
        'message': 'Payment processed successfully',
        'bill': BillDetailSerializer(bill).data,
        'payment': PaymentSerializer(payment).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_appointment_payment(request):
    """
    Initiate payment for an appointment
    """
    # Extract data from request
    appointment_id = request.data.get('appointment_id')
    
    if not appointment_id:
        return Response({
            'error': 'Appointment ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get appointment
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check if user is authorized to pay for this appointment
    if appointment.patient.user != request.user:
        return Response({
            'error': 'Not authorized to pay for this appointment'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if appointment already has a bill
    if hasattr(appointment, 'billing_bill'):
        bill = appointment.billing_bill
    else:
        # Create a new bill for the appointment
        patient = appointment.patient
        doctor = appointment.doctor
        clinic = doctor.clinic
        
        bill = Bill.objects.create(
            bill_number=f'B-{timezone.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:4].upper()}',
            bill_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=7),
            bill_type='appointment',
            patient=patient,
            doctor=doctor,
            clinic=clinic,
            appointment=appointment,
            status='pending'
        )
        
        # Add appointment fee as bill item
        BillItem.objects.create(
            bill=bill,
            item_name=f'Consultation with Dr. {doctor.user.get_full_name()}',
            description=f'Appointment on {appointment.appointment_date.strftime("%Y-%m-%d %H:%M")}',
            quantity=1,
            unit_price=appointment.fees,
            total=appointment.fees
        )
        
        # Recalculate bill total
        bill.calculate_total()
        bill.save()
    
    # In a real app, we would create a payment intent with the payment gateway
    # For now, we'll just return a mock payment intent ID
    payment_intent_id = f'pi_{uuid.uuid4().hex}'
    
    return Response({
        'payment_intent_id': payment_intent_id,
        'amount': bill.due_amount,
        'currency': 'inr',  # Assuming Indian Rupees
        'bill': BillDetailSerializer(bill).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_appointment_payment(request):
    """
    Confirm payment for an appointment
    """
    # Extract data from request
    appointment_id = request.data.get('appointment_id')
    payment_intent_id = request.data.get('payment_intent_id')
    
    if not appointment_id or not payment_intent_id:
        return Response({
            'error': 'Appointment ID and payment intent ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get appointment and bill
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check if user is authorized to pay for this appointment
    if appointment.patient.user != request.user:
        return Response({
            'error': 'Not authorized to pay for this appointment'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get the bill associated with the appointment
    if hasattr(appointment, 'billing_bill'):
        bill = appointment.billing_bill
    else:
        return Response({
            'error': 'No bill found for this appointment'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # In a real app, we would verify the payment intent with the payment gateway
    # For now, we'll just create a payment record and update the bill status
    payment = Payment.objects.create(
        bill=bill,
        amount=bill.due_amount,
        payment_date=timezone.now(),
        payment_method='card',  # Assuming card payment
        reference_number=payment_intent_id,
        notes='Appointment payment made via mobile app',
        receipt_number=f'R-{uuid.uuid4().hex[:8].upper()}',
        created_by=request.user
    )
    
    # Update bill status
    bill.update_status()
    
    # Update appointment status
    appointment.is_paid = True
    appointment.save()
    
    return Response({
        'success': True,
        'message': 'Payment confirmed successfully',
        'bill': BillDetailSerializer(bill).data,
        'payment': PaymentSerializer(payment).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_billing_summary(request):
    """
    Get billing summary for a doctor
    """
    # Check if user is a doctor
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({
            'error': 'User is not a doctor'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from request
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    
    # Filter bills by date range if provided
    bill_queryset = Bill.objects.filter(doctor=doctor)
    
    if from_date:
        try:
            from_date = timezone.datetime.strptime(from_date, '%Y-%m-%d').date()
            bill_queryset = bill_queryset.filter(bill_date__gte=from_date)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date = timezone.datetime.strptime(to_date, '%Y-%m-%d').date()
            bill_queryset = bill_queryset.filter(bill_date__lte=to_date)
        except ValueError:
            pass
    
    # Calculate billing statistics
    total_bills = bill_queryset.count()
    pending_bills = bill_queryset.filter(status='pending').count()
    partial_bills = bill_queryset.filter(status='partial').count()
    paid_bills = bill_queryset.filter(status='paid').count()
    
    total_billed = bill_queryset.filter(status__in=['pending', 'partial', 'paid']).aggregate(
        total=Sum('total'))['total'] or 0
    total_received = bill_queryset.filter(status__in=['partial', 'paid']).aggregate(
        total=Sum('amount_paid'))['total'] or 0
    
    # Get recent bills
    recent_bills = bill_queryset.order_by('-bill_date')[:5]
    
    return Response({
        'doctor_name': doctor.user.get_full_name(),
        'total_bills': total_bills,
        'pending_bills': pending_bills,
        'partial_bills': partial_bills,
        'paid_bills': paid_bills,
        'total_billed': total_billed,
        'total_received': total_received,
        'recent_bills': BillListSerializer(recent_bills, many=True).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_provisional_invoice(request):
    """
    Generate provisional invoice for an appointment
    """
    # Extract data from request
    appointment_id = request.data.get('appointment_id')
    
    if not appointment_id:
        return Response({
            'error': 'Appointment ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get appointment
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check if user is authorized to generate invoice for this appointment
    if not (request.user.is_staff or (appointment.doctor and appointment.doctor.user == request.user)):
        return Response({
            'error': 'Not authorized to generate invoice for this appointment'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if appointment already has a bill
    if hasattr(appointment, 'billing_bill'):
        bill = appointment.billing_bill
    else:
        # Create a new bill for the appointment
        patient = appointment.patient
        doctor = appointment.doctor
        clinic = doctor.clinic
        
        bill = Bill.objects.create(
            bill_number=f'B-{timezone.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:4].upper()}',
            bill_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=7),
            bill_type='consultation',
            patient=patient,
            doctor=doctor,
            clinic=clinic,
            appointment=appointment,
            status='pending'
        )
        
        # Add appointment fee as bill item
        BillItem.objects.create(
            bill=bill,
            item_name=f'Consultation with Dr. {doctor.user.get_full_name()}',
            description=f'Appointment on {appointment.appointment_date.strftime("%Y-%m-%d %H:%M")}',
            quantity=1,
            unit_price=appointment.fees,
            total=appointment.fees
        )
        
        # Recalculate bill total
        bill.calculate_total()
        bill.save()
        
        # Create consultation billing record
        if not ConsultationBilling.objects.filter(appointment=appointment).exists():
            ConsultationBilling.objects.create(
                appointment=appointment,
                bill=bill,
                base_fee=appointment.fees,
                final_fee=appointment.fees,
                doctor=doctor
            )
    
    return Response({
        'success': True,
        'message': 'Provisional invoice generated successfully',
        'bill': BillDetailSerializer(bill).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finalize_invoice(request, pk):
    """
    Finalize an invoice and prepare for payment
    """
    # Get the bill
    bill = get_object_or_404(Bill, pk=pk)
    
    # Check if user is authorized to finalize this invoice
    if not (request.user.is_staff or (bill.doctor and bill.doctor.user == request.user)):
        return Response({
            'error': 'Not authorized to finalize this invoice'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if invoice is in a valid state
    if bill.status not in ['pending', 'partial']:
        return Response({
            'error': f'Cannot finalize invoice with status "{bill.status}"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Add any additional items provided in the request
    added_items = request.data.get('items', [])
    
    for item_data in added_items:
        item_name = item_data.get('name')
        description = item_data.get('description', '')
        quantity = item_data.get('quantity', 1)
        unit_price = item_data.get('unit_price')
        
        if not item_name or not unit_price:
            continue
        
        # Convert price to decimal if it's not
        try:
            unit_price = float(unit_price)
        except (ValueError, TypeError):
            continue
        
        # Add the item to the bill
        BillItem.objects.create(
            bill=bill,
            item_name=item_name,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            total=quantity * unit_price
        )
    
    # Recalculate bill total
    bill.calculate_total()
    bill.save()
    
    return Response({
        'success': True,
        'message': 'Invoice finalized successfully',
        'bill': BillDetailSerializer(bill).data
    })


@api_view(['POST'])
def payment_webhook(request):
    """
    Webhook for payment gateway callbacks.
    """
    # In a real implementation, we would verify the signature of the webhook
    # and handle various event types (payment success, failure, refund, etc.)
    
    event_type = request.data.get('type')
    data = request.data.get('data', {})
    
    if event_type == 'payment_intent.succeeded':
        payment_intent_id = data.get('id')
        metadata = data.get('metadata', {})
        
        # Handle different types of payments based on metadata
        if metadata.get('type') == 'appointment_prepayment':
            appointment_id = metadata.get('appointment_id')
            if appointment_id:
                try:
                    appointment = Appointment.objects.get(id=appointment_id)
                    confirm_appointment_payment(appointment, payment_intent_id)
                except Exception as e:
                    # Log the error but don't return an error response to the webhook
                    print(f"Error processing appointment payment webhook: {str(e)}")
        
        elif metadata.get('type') == 'invoice_payment':
            bill_id = metadata.get('bill_id')
            if bill_id:
                try:
                    bill = Bill.objects.get(id=bill_id)
                    record_invoice_payment(bill, payment_intent_id)
                except Exception as e:
                    # Log the error but don't return an error response to the webhook
                    print(f"Error processing invoice payment webhook: {str(e)}")
    
    # Always return a 200 response to webhooks
    return Response({'status': 'success'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def patient_bills_api(request):
    """
    API endpoint for patients to view their bills.
    """
    try:
        patient = request.user.patient
        bills = Bill.objects.filter(patient=patient).order_by('-bill_date')
        
        # Calculate totals
        total_billed = bills.aggregate(Sum('total'))['total__sum'] or 0
        total_paid = Payment.objects.filter(bill__patient=patient).aggregate(Sum('amount'))['amount__sum'] or 0
        total_pending = total_billed - total_paid
        
        # Serialize the bills
        serializer = BillListSerializer(bills, many=True)
        
        return Response({
            'bills': serializer.data,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'total_pending': total_pending
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsDoctor])
def doctor_billing_summary_api(request):
    """
    API endpoint for doctors to view their billing summary.
    """
    try:
        doctor = request.user.doctor
        
        # Get date range filters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Filter bills based on date range
        bills = Bill.objects.filter(doctor=doctor)
        if from_date:
            bills = bills.filter(bill_date__gte=from_date)
        if to_date:
            bills = bills.filter(bill_date__lte=to_date)
        
        # Calculate statistics
        total_bills = bills.count()
        total_amount = bills.aggregate(Sum('total'))['total__sum'] or 0
        paid_amount = bills.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        pending_amount = total_amount - paid_amount
        
        # Serialize the recent bills
        recent_bills = bills.order_by('-bill_date')[:10]
        serializer = BillListSerializer(recent_bills, many=True)
        
        return Response({
            'total_bills': total_bills,
            'total_amount': total_amount,
            'paid_amount': paid_amount,
            'pending_amount': pending_amount,
            'recent_bills': serializer.data
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST) 