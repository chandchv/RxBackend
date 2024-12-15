from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Prescription, Doctor, Patient
from ..serializers import PrescriptionSerializer
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_prescription(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    patient_id = request.data.get('patient_id')
    patient = get_object_or_404(Patient, id=patient_id)

    prescription = Prescription(
        doctor=doctor,
        patient=patient,
        medication=request.data.get('medication'),
        dosage=request.data.get('dosage'),
        instructions=request.data.get('instructions')
    )
    prescription.save()

    return Response({'success': True, 'prescription_id': prescription.id}, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prescriptions(request, patient_id):
    prescriptions = Prescription.objects.filter(patient_id=patient_id)
    serializer = PrescriptionSerializer(prescriptions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK) 

@login_required
def prescriptions_view(request):
    return render(request, 'prescription.html')

@login_required
def prescription_detail(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    return render(request, 'prescription_detail.html', {'prescription': prescription})

@login_required
def prescription_edit(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    return render(request, 'prescription_edit.html', {'prescription': prescription})