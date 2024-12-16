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

@api_view(['GET'])
def available_slots(request, doctor_id, date):
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get all booked appointments for the selected date
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__date=selected_date
        ).values_list('appointment_date__time', flat=True)
        
        # Generate available time slots (example: 9 AM to 5 PM, 30-minute intervals)
        all_slots = []
        start_time = timezone.datetime.combine(selected_date, timezone.datetime.min.time().replace(hour=9))
        end_time = timezone.datetime.combine(selected_date, timezone.datetime.min.time().replace(hour=17))
        
        current_slot = start_time
        while current_slot < end_time:
            if current_slot.time() not in booked_slots:
                all_slots.append(current_slot.strftime('%H:%M'))
            current_slot += timedelta(minutes=30)
        
        return Response({'slots': all_slots})
        
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400) 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_appointment(request, appointment_id):
    try:
        appointment = get_object_or_404(Appointment, 
                                      id=appointment_id, 
                                      patient__user=request.user)
        
        if appointment.status == 'scheduled':
            appointment.status = 'cancelled'
            appointment.save()
            return Response({'success': True})
        
        return Response(
            {'error': 'Appointment cannot be cancelled'}, 
            status=400
        )
        
    except Exception as e:
        return Response({'error': str(e)}, status=400) 