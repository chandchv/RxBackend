from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from ..models import Lab, LabStaff
from ..serializers import LabSerializer, LabStaffSerializer

class LabManagementViewSet(viewsets.ModelViewSet):
    serializer_class = LabSerializer

    def get_queryset(self):
        if hasattr(self.request.user, 'clinicadmin'):
            return Lab.objects.filter(clinic=self.request.user.clinicadmin.clinic)
        return Lab.objects.none()

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.user.clinicadmin.clinic)

    @action(detail=True, methods=['post'])
    def create_staff(self, request, pk=None):
        lab = self.get_object()
        
        try:
            user = User.objects.create_user(
                username=request.data.get('username'),
                email=request.data.get('email'),
                password=request.data.get('password'),
                first_name=request.data.get('first_name'),
                last_name=request.data.get('last_name')
            )

            lab_staff = LabStaff.objects.create(
                user=user,
                lab=lab,
                role=request.data.get('role'),
                specialization=request.data.get('specialization', '')
            )

            return Response(LabStaffSerializer(lab_staff).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True)
    def staff_list(self, request, pk=None):
        lab = self.get_object()
        staff = LabStaff.objects.filter(lab=lab)
        return Response(LabStaffSerializer(staff, many=True).data) 