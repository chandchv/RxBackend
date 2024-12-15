from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Appointment, Patient
from ..serializers import AppointmentSerializer
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from users.forms import AppointmentForm

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
def create_appointment(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users:appointments_list')
    else:
        form = AppointmentForm()
    return render(request, 'appointments/create_appointment.html', {'form': form}) 