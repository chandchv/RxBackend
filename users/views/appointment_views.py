from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Appointment, Patient, Doctor
from ..serializers import AppointmentSerializer
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from users.forms import AppointmentForm
from django.contrib import messages
from datetime import datetime

class AppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        appointments = Appointment.objects.all()
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AppointmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AppointmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            appointments = Appointment.objects.all()
            serializer = AppointmentSerializer(appointments, many=True)
            return Response({
                'status': 'success',
                'data': serializer.data
            })
        except Exception as e:
            print(f"Error in AppointmentListView: {str(e)}")  # Debug log
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AppointmentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    template_name = 'create_appointment.html'

    def get(self, request):
        return render(request, self.template_name, {
            'patients': Patient.objects.all()
        })

    def post(self, request):
        serializer = AppointmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(doctor=request.user)
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    '<div class="alert alert-success">Appointment created successfully!</div>'
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="alert alert-danger">Error creating appointment</div>'
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@login_required
def appointments_view(request):
    appointments = Appointment.objects.all()
   
    patients = Patient.objects.all()

    return render(request, 'appointments.html', {'appointments': appointments, 'patients': patients})

@login_required
def create_appointment(request):
    clinic = request.user.userprofile.clinic
    patients = Patient.objects.filter(clinic=clinic)
    
    if request.method == 'POST':
        try:
            appointment = Appointment.objects.create(
                patient_id=request.POST['patient'],
                doctor=request.user.doctor,
                appointment_date=datetime.strptime(
                    f"{request.POST['appointment_date']} {request.POST['appointment_time']}", 
                    "%Y-%m-%d %H:%M"
                ),
                reason=request.POST.get('reason', ''),
                status='scheduled'
            )
            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('users:appointments')
        except Exception as e:
            messages.error(request, f'Error scheduling appointment: {str(e)}')
    
    return render(request, 'appointments/create_appointment.html', {
        'patients': patients
    }) 

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    return render(request, 'appointments/appointment_detail.html', {'appointment': appointment})

@login_required
def appointment_delete(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.delete()
    return redirect('users:appointments')
