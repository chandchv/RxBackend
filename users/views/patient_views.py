from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Patient
from ..forms import PatientForm
from ..serializers import PatientSerializer

@login_required
def create_patient(request):
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users:patients_list')
    else:
        form = PatientForm()
    return render(request, 'create_patient.html', {'form': form})

@api_view(['GET'])
#@permission_classes([IsAuthenticated])
def get_patients(request):
    patients = Patient.objects.all()
    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data) 

@login_required
def patients_list(request):
    return render(request, 'patients.html')

