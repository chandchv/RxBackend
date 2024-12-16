from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from ..models import Doctor, Appointment
from ..serializers import AppointmentSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_list(request):
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        appointments = Appointment.objects.filter(doctor=doctor).order_by('appointment_date')
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_appointment_status(request, appointment_id):
    try:
        doctor = get_object_or_404(Doctor, user=request.user)
        appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor)
        
        new_status = request.data.get('status')
        if new_status in ['scheduled', 'completed', 'cancelled']:
            appointment.status = new_status
            appointment.save()
            return Response({'success': True})
        return Response(
            {'error': 'Invalid status'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 