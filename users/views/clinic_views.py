from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import default_storage
from ..models import Clinic, Doctor
from ..serializers import ClinicSettingsSerializer

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def clinic_settings(request):
    try:
        doctor = request.user.doctor
        clinic = doctor.clinic

        if request.method == 'GET':
            serializer = ClinicSettingsSerializer(clinic)
            return Response(serializer.data)

        elif request.method == 'PUT':
            serializer = ClinicSettingsSerializer(clinic, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_clinic_logo(request):
    try:
        doctor = request.user.doctor
        clinic = doctor.clinic
        
        if 'logo' not in request.FILES:
            return Response({
                'error': 'No logo file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        logo_file = request.FILES['logo']
        
        # Save the new logo
        file_path = f'clinic_logos/{clinic.id}/{logo_file.name}'
        file_path = default_storage.save(file_path, logo_file)
        
        # Update clinic logo path
        clinic.logo = file_path
        clinic.save()
        
        return Response({
            'message': 'Logo uploaded successfully',
            'logo_url': clinic.logo.url
        })

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST) 