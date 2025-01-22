from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from ..models import Clinic, Doctor, Staff, UserProfile
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from ..scripts.scrapeGpt01 import verify_doctor as verify_doctor_api
from ..constants import MEDICAL_COUNCILS  # Import the constants
import json
import string
import random
from django.db import transaction, IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Patient, Staff, Appointment, Doctor
from ..permissions import IsClinicAdmin



def is_superuser(user):
    return user.is_superuser

def clinic_admin_dashboard(request):
    """Main clinic administration dashboard view"""
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You don't have permission to access the admin panel.")
        return redirect('users:dashboard')
        
    today = timezone.now().date()
    
    # Get current clinic
    if request.user.is_superuser:
        current_clinic_id = request.session.get('current_clinic_id')
        if not current_clinic_id:
            # Default to first clinic if none selected
            first_clinic = Clinic.objects.first()
            if first_clinic:
                current_clinic_id = first_clinic.id
                request.session['current_clinic_id'] = current_clinic_id
    else:
        # Non-superuser sees their assigned clinic
        current_clinic_id = request.user.profile.clinic.id if hasattr(request.user, 'profile') else None

    if current_clinic_id:
        clinic = get_object_or_404(Clinic, id=current_clinic_id)
        # Get doctors for this clinic
        clinic_doctors = Doctor.objects.filter(clinic=clinic)
        
        context = {
            'doctors_count': clinic_doctors.count(),
            'staff_count': Staff.objects.filter(clinic=clinic).count(),
            'patients_count': Patient.objects.filter(clinic=clinic).count(),
            'todays_appointments': Appointment.objects.filter(
                doctor__in=clinic_doctors,  # Filter appointments by clinic's doctors
                appointment_date=today
            ).count(),
            'clinic_name': clinic.name,
            'clinic_logo': clinic.logo.url if clinic.logo else None,
            'current_clinic_id': current_clinic_id,
        }
        
        if request.user.is_superuser:
            context['clinic_list'] = Clinic.objects.all()
    else:
        messages.error(request, "No clinic assigned.")
        return redirect('users:dashboard')
    
    return render(request, 'clinic_admin/admin_dashboard.html', context)

@login_required
def clinic_profile(request):
    """View and update clinic profile"""
    user_profile = request.user.profile
    clinic = user_profile.clinic
    

    if request.method == 'POST':
        if not clinic:
            # Create new clinic
            clinic = Clinic.objects.create(
                name=request.POST.get('name'),
                address=request.POST.get('address'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email'),
                registration_number=request.POST.get('registration_number')
            )
            user_profile.clinic = clinic
            user_profile.save()
        else:
            # Update existing clinic
            clinic.name = request.POST.get('name')
            clinic.address = request.POST.get('address')
            clinic.phone_number = request.POST.get('phone_number')
            clinic.email = request.POST.get('email')
            clinic.registration_number = request.POST.get('registration_number')
            
        if 'logo' in request.FILES:
            clinic.logo = request.FILES['logo']
        clinic.save()
        
        messages.success(request, 'Clinic profile updated successfully!')
        return redirect('users:clinic_admin_dashboard')
        
    return render(request, 'clinic_admin/clinic_profile.html', {'clinic': clinic})

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

@login_required
def add_doctor(request):
    """Add new doctor view"""
    clinic = request.user.profile.clinic
    
    if request.method == 'POST':
        try:
            # Get verification data
            verified_data = json.loads(request.POST.get('verified_data', '{}'))
            print("Verified data:", verified_data)  # Debug print
            
            # Get form data
            email = request.POST.get('email')
            specialization = request.POST.get('specialization', '')
            consultation_fee = request.POST.get('consultation_fee', 0)
            
            if not email:
                raise ValueError("Email is required")
            
            # Check if user already exists
            if User.objects.filter(username=email).exists():
                raise ValueError("A user with this email already exists")
            
            if User.objects.filter(email=email).exists():
                raise ValueError("This email is already registered")
                
            # Generate random password
            random_password = generate_random_password()
            
            # Create user
            name_parts = verified_data.get('name', '').split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            # Create user with transaction
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=random_password
                )
                
                # Create doctor profile
                doctor = Doctor.objects.create(
                    user=user,
                    clinic=clinic,
                    name=verified_data.get('name', ''),
                    specialization=specialization,
                    license_number=verified_data.get('registration_number', ''),
                    medical_council=verified_data.get('state_council', ''),
                    consultation_fee=consultation_fee,
                    verified=True,
                    verification_details=verified_data
                )
                
                # Handle profile picture
                if 'profile_picture' in request.FILES:
                    doctor.profile_picture = request.FILES['profile_picture']
                    doctor.save()
            
            messages.success(request, 'Doctor added successfully!')
            # Store password in session temporarily
            request.session['initial_password'] = random_password
            
            # Redirect to doctor details page
            return redirect('users:doctor_details', doctor_id=doctor.id)
            
        except ValueError as e:
            messages.error(request, str(e))
        except IntegrityError:
            messages.error(request, "A user with this email already exists")
        except json.JSONDecodeError:
            messages.error(request, "Invalid verification data")
        except Exception as e:
            print(f"Error adding doctor: {str(e)}")
            messages.error(request, f'Error adding doctor: {str(e)}')
    
    return render(request, 'clinic_admin/add_doctor.html', {
        'medical_councils': MEDICAL_COUNCILS
    })

@login_required
def doctors_list(request):
    """View and manage doctors"""
    doctors = Doctor.objects.all().order_by('name')
    return render(request, 'clinic_admin/doctors_list.html', {'doctors': doctors})

@login_required
def add_staff(request):
    """Add new staff member"""
    clinic = request.user.profile.clinic
    

    if not clinic:
        messages.error(request, "Please set up your clinic first.")
        return redirect('users:clinic_profile')
    
    if request.method == 'POST':
        try:
            # Create user for staff member
            user = User.objects.create_user(
                username=request.POST.get('email'),
                email=request.POST.get('email'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                password=generate_random_password()  # Generate random password
            )
            
            staff = Staff.objects.create(
                user=user,
                clinic=clinic,
                role=request.POST.get('role'),
                joining_date=request.POST.get('joining_date')
            )
            
            messages.success(request, 'Staff member added successfully!')
            return redirect('users:staff_list')
        except Exception as e:
            messages.error(request, f'Error adding staff member: {str(e)}')
    
    return render(request, 'clinic_admin/add_staff.html')

@login_required
def staff_list(request):
    """View and manage staff members"""
    staff = Staff.objects.all().order_by('role')
    return render(request, 'clinic_admin/staff_list.html', {'staff': staff})

def get_recent_activities():
    """Helper function to get recent activities"""
    # This is a placeholder - implement actual activity tracking
    return [] 

@login_required
@require_POST
def delete_doctor(request, doctor_id):
    """Delete a doctor"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        doctor.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def edit_doctor(request, doctor_id):
    """Edit doctor details"""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    
    if request.method == 'POST':
        try:
            doctor.name = request.POST.get('name')
            doctor.specialization = request.POST.get('specialization')
            doctor.license_number = request.POST.get('license_number')
            doctor.medical_council = request.POST.get('medical_council')
            doctor.consultation_fee = request.POST.get('consultation_fee')
            
            if 'profile_picture' in request.FILES:
                doctor.profile_picture = request.FILES['profile_picture']
                
            doctor.save()
            messages.success(request, 'Doctor updated successfully!')
            return redirect('users:doctors_list')
        except Exception as e:
            messages.error(request, f'Error updating doctor: {str(e)}')
    
    return render(request, 'clinic_admin/edit_doctor.html', {'doctor': doctor})

@login_required
def edit_staff(request, staff_id):
    """Edit staff member details"""
    staff = get_object_or_404(Staff, id=staff_id)
    
    if request.method == 'POST':
        try:
            staff.role = request.POST.get('role')
            staff.joining_date = request.POST.get('joining_date')
            staff.user.first_name = request.POST.get('first_name')
            staff.user.last_name = request.POST.get('last_name')
            staff.user.email = request.POST.get('email')
            
            staff.user.save()
            staff.save()
            
            messages.success(request, 'Staff member updated successfully!')
            return redirect('users:staff_list')
        except Exception as e:
            messages.error(request, f'Error updating staff member: {str(e)}')
    
    return render(request, 'clinic_admin/edit_staff.html', {'staff': staff})

@login_required
@require_POST
def toggle_staff_status(request, staff_id):
    """Toggle staff member active status"""
    try:
        staff = get_object_or_404(Staff, id=staff_id)
        staff.is_active = not staff.is_active
        staff.save()
        return JsonResponse({'success': True, 'is_active': staff.is_active})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400) 

@login_required
@require_POST
def verify_doctor(request, doctor_id):
    """Verify a doctor's credentials"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        doctor.verified = True
        doctor.save()
        messages.success(request, f'Dr. {doctor.name} has been verified successfully.')
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def doctor_verification_details(request, doctor_id):
    """View doctor's verification details"""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    return render(request, 'clinic_admin/doctor_verification.html', {'doctor': doctor}) 

@login_required
@require_POST
def verify_doctor_credentials(request):
    """Verify doctor credentials during addition"""
    try:
        import json
        import re
        from datetime import datetime
        data = json.loads(request.body)
        
        # Format the data for verification
        doctor_details = {
            'name': data.get('name'),
            'registration_number': data.get('registration_number'),
            'state_council': data.get('state_council')
        }
        
        print("\n=== Verification Request ===")
        print("Doctor details:", doctor_details)
        
        # Import and call verification function
        success, result = verify_doctor_api(doctor_details)
        
        if success and isinstance(result, dict):
            # Parse license number and registration date
            license_info = result.get('registration_number', '')
            
            # Extract license number and date using regex
            license_match = re.search(r'(\d+)\s+Date of Reg\.\s+(\d{2}/\d{2}/\d{4})', license_info)
            
            if license_match:
                license_number = license_match.group(1)
                reg_date = license_match.group(2)
                
                # Convert date string to proper format
                try:
                    reg_date_obj = datetime.strptime(reg_date, '%d/%m/%Y')
                    formatted_reg_date = reg_date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    formatted_reg_date = None
            else:
                license_number = license_info
                formatted_reg_date = None
            
            return JsonResponse({
                'verified': True,
                'verification_data': {
                    'name': result.get('name', ''),
                    'father_name': result.get('father_name', ''),
                    'date_of_birth': result.get('date_of_birth', ''),
                    'registration_number': license_number.strip(),  # Clean license number
                    'registration_date': formatted_reg_date,  # Add parsed registration date
                    'state_council': result.get('state_council', ''),
                    'qualification': result.get('qualification', ''),
                    'qualification_year': result.get('qualification_year', ''),
                    'university': result.get('university', ''),
                    'permanent_address': result.get('permanent_address', '')
                }
            })
        else:
            return JsonResponse({
                'verified': False,
                'message': str(result) if result else 'Verification failed'
            })
            
    except Exception as e:
        print(f"Verification error: {str(e)}")
        return JsonResponse({
            'verified': False,
            'message': f"Error during verification: {str(e)}"
        })

@login_required
def doctor_details(request, doctor_id):
    """View doctor details"""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    
    context = {
        'doctor': doctor,
        'initial_password': request.session.pop('initial_password', None)  # Get and remove password from session
    }
    return render(request, 'clinic_admin/doctor_details.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def dashboard_stats(request):
    try:
        clinic = request.user.clinic
        today = timezone.now().date()
        
        # Get counts
        doctor_count = Doctor.objects.filter(clinic=clinic).count()
        patient_count = Patient.objects.filter(clinic=clinic).count()
        staff_count = Staff.objects.filter(clinic=clinic).count()
        appointment_count = Appointment.objects.filter(clinic=clinic).count()
        
        # Get today's stats
        today_appointments = Appointment.objects.filter(
            clinic=clinic,
            appointment_date__date=today
        ).count()
        
        today_patients = Patient.objects.filter(
            clinic=clinic,
            created_at__date=today
        ).count()

        return Response({
            'doctorCount': doctor_count,
            'patientCount': patient_count,
            'staffCount': staff_count,
            'appointmentCount': appointment_count,
            'todayAppointments': today_appointments,
            'todayPatients': today_patients
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def clinic_admin_dashboard_api(request):
    """API endpoint for clinic administration dashboard"""
    try:
        today = timezone.now().date()
        
        # Get counts
        doctors_count = Doctor.objects.count()
        staff_count = Staff.objects.count()
        patients_count = Patient.objects.count()
        todays_appointments = Appointment.objects.filter(
            appointment_date=today
        ).count()
        pending_appointments = Appointment.objects.filter(
            status='PENDING'
        ).count()

        # Prepare response data
        dashboard_data = {
            'totalDoctors': doctors_count,
            'totalStaff': staff_count,
            'totalPatients': patients_count,
            'todayAppointments': todays_appointments,
            'pendingAppointments': pending_appointments,
            'lastUpdated': timezone.now().isoformat()
        }
        
        return Response(dashboard_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Dashboard API error: {str(e)}")  # Debug print
        return Response({
            'error': 'Failed to fetch dashboard data',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def doctor_list_api(request):
    """API endpoint to list all doctors"""
    try:
        doctors = Doctor.objects.all()
        doctor_data = []
        
        for doctor in doctors:
            doctor_data.append({
                'id': doctor.id,
                'user_id': doctor.user.id,
                'first_name': doctor.user.first_name,
                'last_name': doctor.user.last_name,
                'email': doctor.user.email,
                'specialization': doctor.specialization,
                'phone_number': doctor.phone_number,
                'status': doctor.status,
                'clinic': doctor.clinic.name if doctor.clinic else None,
            })
        
        return Response(doctor_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Doctor list API error: {str(e)}")  # Debug print
        return Response({
            'error': 'Failed to fetch doctors',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@require_POST
@user_passes_test(is_superuser)
def change_clinic(request, clinic_id):
    """Change the current clinic for superuser"""
    try:
        clinic = get_object_or_404(Clinic, id=clinic_id)
        request.session['current_clinic_id'] = clinic_id
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@user_passes_test(is_superuser)
def edit_clinic_profile(request, clinic_id):
    """Edit clinic profile view"""
    clinic = get_object_or_404(Clinic, id=clinic_id)
    
    if request.method == 'POST':
        form = ClinicProfileForm(request.POST, request.FILES, instance=clinic)
        if form.is_valid():
            form.save()
            messages.success(request, "Clinic profile updated successfully.")
            return redirect('users:clinic_admin_dashboard')
    else:
        form = ClinicProfileForm(instance=clinic)
    
    return render(request, 'clinic_admin/edit_clinic_profile.html', {
        'form': form,
        'clinic': clinic
    })