from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from ..models import Lab, LabStaff, LabRegistration
from ..serializers import LabSerializer, LabStaffSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from ..forms import LabRegistrationForm
from django.utils import timezone

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

def lab_registration(request):
    if request.method == 'POST':
        form = LabRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            registration = form.save()
            messages.success(request, 'Your lab registration request has been submitted. We will review it shortly.')
            return redirect('users:lab_registration_success')
    else:
        form = LabRegistrationForm()
    
    return render(request, 'lab/registration.html', {'form': form})

def lab_registration_success(request):
    return render(request, 'lab/registration_success.html')

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def lab_verification_list(request):
    registrations = LabRegistration.objects.filter(status='PENDING').order_by('created_at')
    return render(request, 'lab/verification_list.html', {'registrations': registrations})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def verify_lab(request, registration_id):
    registration = get_object_or_404(LabRegistration, id=registration_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('verification_notes', '')
        
        if action == 'approve':
            registration.status = 'APPROVED'
            registration.verification_notes = notes
            registration.verified_by = request.user
            registration.verification_date = timezone.now()
            registration.save()
            
            # Create lab profile
            lab = Lab.objects.create(
                name=registration.name,
                email=registration.email,
                phone_number=registration.phone_number,
                address=registration.address,
                city=registration.city,
                state=registration.state,
                pincode=registration.pincode,
                registration_number=registration.registration_number,
                gst_number=registration.gst_number,
                is_active=True
            )
            
            messages.success(request, f'Lab {registration.name} has been approved and added to the system.')
        elif action == 'reject':
            registration.status = 'REJECTED'
            registration.verification_notes = notes
            registration.verified_by = request.user
            registration.verification_date = timezone.now()
            registration.save()
            messages.success(request, f'Lab {registration.name} has been rejected.')
        
        return redirect('users:lab_verification_list')
    
    return render(request, 'lab/verify_lab.html', {'registration': registration}) 