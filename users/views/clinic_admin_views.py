from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from ..decorators import user_is_admin
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from ..scripts.scrapeGpt1 import verify_doctor as verify_doctor_api
from ..constants import MEDICAL_COUNCILS  # Import the constants 
import json
import string
import random
from django.db import transaction, IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from ..models import Clinic, Doctor, DoctorLeave, Lab, LabStaff, LabTest, Patient, Appointment, Staff, StaffLeave
from ..permissions import IsClinicAdmin
from ..forms import ClinicProfileForm, DoctorForm, LabForm  # We'll create this form
from notifications.models import Notification



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
        
        # New lab-related context data
        labs_count = Lab.objects.filter(clinic=clinic).count()
        active_tests_count = LabTest.objects.filter(
            prescription__doctor__doctor__clinic=clinic,
            status__in=['REQUESTED', 'PROCESSING']
        ).count()
        pending_tests_count = LabTest.objects.filter(
            prescription__doctor__doctor__clinic=clinic,
            status='REQUESTED'
        ).count()
        today_tests_count = LabTest.objects.filter(
            prescription__doctor__doctor__clinic=clinic,
            created_at__date=today
        ).count()
        active_lab_staff_count = LabStaff.objects.filter(
            lab__clinic=clinic,
            is_active=True
        ).count()
        recent_lab_tests = LabTest.objects.filter(
            prescription__doctor__doctor__clinic=clinic
        ).order_by('-created_at')[:5]
        
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
            'labs_count': labs_count,
            'active_tests_count': active_tests_count,
            'pending_tests_count': pending_tests_count,
            'today_tests_count': today_tests_count,
            'active_lab_staff_count': active_lab_staff_count,
            'recent_lab_tests': recent_lab_tests,
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
    if not hasattr(request.user, 'clinic_admin'):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('users:dashboard')
        
    clinic = request.user.clinic_admin.clinic
    
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
            request.user.clinic_admin.clinic = clinic
            request.user.clinic_admin.save()
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
    try:
        # Get current clinic
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                # Default to first clinic if none selected
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            clinic = get_object_or_404(Clinic, id=current_clinic_id)
        else:
            # For regular admins, get their assigned clinic
            if not hasattr(request.user, 'profile') or not request.user.profile.clinic:
                messages.error(request, "No clinic assigned to your account")
                return redirect('users:clinic_admin_dashboard')
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
            'medical_councils': MEDICAL_COUNCILS,
            'clinic': clinic
        })
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
def doctors_list(request):
    """View and manage doctors"""
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
        current_clinic = Clinic.objects.get(id=current_clinic_id)
        doctors = Doctor.objects.filter(clinic=current_clinic).order_by('name')
        context = {
            'doctors': doctors,
            'current_clinic': current_clinic,
            'clinic_list': Clinic.objects.all() if request.user.is_superuser else None
        }
        return render(request, 'clinic_admin/doctors_list.html', context)
    else:
        messages.error(request, "No clinic assigned.")
        return redirect('users:dashboard')

@login_required
def add_staff(request):
    """Add new staff member"""
    try:
        # Get current clinic
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                # Default to first clinic if none selected
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            clinic = get_object_or_404(Clinic, id=current_clinic_id)
            clinic_list = Clinic.objects.all()
        else:
            # For regular admins, get their assigned clinic
            if not hasattr(request.user, 'clinic_admin') or not request.user.clinic_admin.clinic:
                messages.error(request, "No clinic assigned to your account")
                return redirect('users:clinic_admin_dashboard')
            clinic = request.user.clinic_admin.clinic
            clinic_list = None
        
        if request.method == 'POST':
            try:
                email = request.POST.get('email')
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                role = request.POST.get('role')
                joining_date = request.POST.get('joining_date')
                clinic_id = request.POST.get('clinic_id')
                is_clinic_admin = request.POST.get('is_clinic_admin') == 'on'
                is_lab_admin = request.POST.get('is_lab_admin') == 'on'
                staff_id = request.POST.get('staff_id')

                # Check if user with this email already exists
                if User.objects.filter(email=email).exists():
                    messages.error(request, "A user with this email already exists")
                    return render(request, 'clinic_admin/add_staff.html', {
                        'clinic': clinic,
                        'clinic_list': clinic_list,
                        'current_clinic': clinic
                    })

                # Check if staff_id already exists
                if Staff.objects.filter(staff_id=staff_id).exists():
                    messages.error(request, "A staff member with this ID already exists")
                    return render(request, 'clinic_admin/add_staff.html', {
                        'clinic': clinic,
                        'clinic_list': clinic_list,
                        'current_clinic': clinic
                    })

                # Create user for staff member with unique username
                username = email  # Use email as username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{email}_{counter}"
                    counter += 1

                # Generate random password
                password = generate_random_password()

                # Create user with the generated password
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    is_staff=False,  # Don't give admin access
                    is_active=True
                )
                
                # Get the selected clinic for superusers
                if request.user.is_superuser and clinic_id:
                    selected_clinic = get_object_or_404(Clinic, id=clinic_id)
                else:
                    selected_clinic = clinic
                
                # Create staff profile
                staff = Staff.objects.create(
                    user=user,
                    clinic=selected_clinic,
                    role=role,
                    joining_date=joining_date,
                    is_clinic_admin=is_clinic_admin,
                    is_lab_admin=is_lab_admin,
                    staff_id=staff_id
                )
                
                # Store credentials in session to display
                request.session['new_staff_credentials'] = {
                    'username': username,
                    'password': password
                }
                
                messages.success(request, 'Staff member added successfully!')
                return redirect('users:staff_credentials')
                
            except Exception as e:
                messages.error(request, f'Error adding staff member: {str(e)}')
                return render(request, 'clinic_admin/add_staff.html', {
                    'clinic': clinic,
                    'clinic_list': clinic_list,
                    'current_clinic': clinic
                })
        
        return render(request, 'clinic_admin/add_staff.html', {
            'clinic': clinic,
            'clinic_list': clinic_list,
            'current_clinic': clinic
        })
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
def staff_credentials(request):
    """Display staff credentials after creation"""
    credentials = request.session.pop('new_staff_credentials', None)
    if not credentials:
        messages.error(request, "No credentials found. Please add a staff member first.")
        return redirect('users:add_staff')
    
    return render(request, 'clinic_admin/staff_credentials.html', {
        'username': credentials['username'],
        'password': credentials['password']
    })

@login_required
def staff_list(request):
    """View and manage staff members"""
    try:
        if request.user.is_superuser:
            # Get current clinic from session or default to first clinic
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            
            if current_clinic_id:
                current_clinic = Clinic.objects.get(id=current_clinic_id)
                staff = Staff.objects.filter(clinic=current_clinic).order_by('role')
                
                # Get all clinics for superuser
                clinic_list = Clinic.objects.all()
                
                # Handle clinic change
                if request.method == 'POST' and 'clinic_id' in request.POST:
                    new_clinic_id = request.POST.get('clinic_id')
                    if new_clinic_id:
                        request.session['current_clinic_id'] = new_clinic_id
                        return redirect('users:staff_list')
                    
                # Handle clinic assignment
                if request.method == 'POST' and 'assign_clinic' in request.POST:
                    staff_id = request.POST.get('staff_id')
                    new_clinic_id = request.POST.get('assign_clinic')
                    if staff_id and new_clinic_id:
                        staff_member = Staff.objects.get(id=staff_id)
                        new_clinic = Clinic.objects.get(id=new_clinic_id)
                        staff_member.clinic = new_clinic
                        staff_member.save()
                        messages.success(request, f'Staff member assigned to {new_clinic.name} successfully')
                        return redirect('users:staff_list')
            else:
                staff = Staff.objects.none()
                clinic_list = None
        else:
            # Non-superuser sees their assigned clinic
            current_clinic = request.user.clinic_admin.clinic
            staff = Staff.objects.filter(clinic=current_clinic).order_by('role')
            clinic_list = None
        
        context = {
            'staff': staff,
            'current_clinic': current_clinic if 'current_clinic' in locals() else None,
            'clinic_list': clinic_list,
            'all_clinics': Clinic.objects.all() if request.user.is_superuser else None
        }
        
        return render(request, 'clinic_admin/staff_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Error accessing staff list: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

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
            print("Raw verification result:", result)
            
            # Format registration date
            reg_date = result.get('registration_date')
            try:
                if reg_date:
                    reg_date_obj = datetime.strptime(reg_date, '%d/%m/%Y')
                    formatted_reg_date = reg_date_obj.strftime('%Y-%m-%d')
                else:
                    formatted_reg_date = None
            except ValueError:
                formatted_reg_date = None
            
            # Format verification response
            verification_data = {
                'name': result.get('name', ''),
                'registration_number': result.get('registration', ''),  # Changed from registration_number
                'council': result.get('council', ''),  # Added council
                'qualification': result.get('qualification', ''),
                'registration_date': formatted_reg_date,
                'father_name': result.get('father_name', ''),
                'date_of_birth': result.get('date_of_birth', ''),
                'university': result.get('university', ''),
                'permanent_address': result.get('permanent_address', ''),
                'qualification_year': result.get('qualification_year', ''),
                'verification_status': result.get('verification_status', 'VERIFIED'),
                'verification_timestamp': result.get('verification_timestamp', '')
            }
            
            print("Formatted verification data:", verification_data)
            
            return JsonResponse({
                'verified': True,
                'verification_data': verification_data
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

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def update_current_clinic(request):
    """API endpoint to get or update current clinic"""
    try:
        if request.method == 'GET':
            clinic_id = request.session.get('current_clinic_id')
            if not clinic_id and request.user.is_superuser:
                clinic = Clinic.objects.first()
                clinic_id = clinic.id if clinic else None
            elif not clinic_id:
                clinic_id = request.user.profile.clinic.id
            return Response({'clinic_id': clinic_id})
            
        elif request.method == 'PUT':
            clinic_id = request.data.get('clinic_id')
            if clinic_id:
                request.session['current_clinic_id'] = clinic_id
                return Response({'clinic_id': clinic_id})
            return Response({'error': 'No clinic_id provided'}, status=400)
            
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinic_admin_dashboard_api(request, clinic_id=None):
    """API endpoint for clinic administration dashboard"""
    try:
        # Get the specified clinic or user's clinic
        if clinic_id and request.user.is_superuser:
            clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            clinic = request.user.profile.clinic
            
        if not clinic:
            return Response({
                'error': 'No clinic found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Get today's date
        today = timezone.now().date()
        
        # Get all related data for the clinic
        doctors = Doctor.objects.filter(clinic=clinic)
        patients = Patient.objects.filter(clinic=clinic)
        staff = Staff.objects.filter(clinic=clinic)
        
        # Get appointments for today
        todays_appointments = Appointment.objects.filter(
            doctor__in=doctors,
            appointment_date=today
        )
        
        # Get pending appointments
        pending_appointments = Appointment.objects.filter(
            doctor__in=doctors,
            status='PENDING'
        )
        
        print(f"Fetching data for clinic {clinic.id}: {clinic.name}")
        print(f"Found: {doctors.count()} doctors, {patients.count()} patients")
        
        dashboard_data = {
            'totalDoctors': doctors.count(),
            'totalPatients': patients.count(),
            'todayAppointments': todays_appointments.count(),
            'pendingAppointments': pending_appointments.count(),
            'totalStaff': staff.count(),
            'clinicName': clinic.name,
            'clinicId': clinic.id,
        }
        
        return Response(dashboard_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Dashboard API error: {str(e)}")
        return Response({
            'error': 'Failed to fetch dashboard data',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_list_api(request, clinic_id=None):
    try:
        if clinic_id and request.user.is_superuser:
            clinic = get_object_or_404(Clinic, id=clinic_id)
        elif request.user.is_superuser:
            clinic = Clinic.objects.first()
        else:
            clinic = request.user.profile.clinic

        doctors = Doctor.objects.filter(clinic=clinic)
        
        doctor_data = []
        for doctor in doctors:
            doctor_data.append({
                'id': doctor.id,
                'name': doctor.name,
                'email': doctor.email,
                'specialization': doctor.specialization,
                'license_number': doctor.license_number,
                'status': 'Active' if doctor.is_active else 'Inactive'
            })

        return Response(doctor_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Doctor list API error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_list_api(request, clinic_id=None):  
    try:
        if clinic_id and request.user.is_superuser:
            clinic = get_object_or_404(Clinic, id=clinic_id)
        elif request.user.is_superuser:
            clinic = Clinic.objects.first()
        else:
            clinic = request.user.profile.clinic

        print(f"Fetching patients for clinic {clinic.id}: {clinic.name}")

        patients = Patient.objects.filter(clinic=clinic)
        
        patient_data = []
        for patient in patients:
            patient_data.append({
                'id': patient.id,
                'name': f"{patient.first_name} {patient.last_name}",
                'phone_number': patient.phone_number,
                'email': patient.email,
                'status': 'Active',
                'doctor': patient.doctor.name if patient.doctor else None,
            })

        return Response(patient_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Patient list API error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_clinic_api(request):
    """API endpoint to create a new clinic"""
    try:
        if not request.user.is_superuser:
            return Response({
                'error': 'Only superusers can create clinics'
            }, status=status.HTTP_403_FORBIDDEN)
            
        # Get data from request
        name = request.data.get('name')
        email = request.data.get('email')
        phone_number = request.data.get('phone_number')
        registration_number = request.data.get('registration_number')
        
        # Validate required fields
        if not name:
            return Response({
                'error': 'Clinic name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create new clinic
        clinic = Clinic.objects.create(
            name=name,
            email=email,
            phone_number=phone_number,
            registration_number=registration_number
        )
        
        return Response({
            'id': clinic.id,
            'name': clinic.name,
            'message': 'Clinic created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"Create clinic error: {str(e)}")
        return Response({
            'error': 'Failed to create clinic',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clinics_api(request):
    """API endpoint to get list of clinics"""
    try:
        # For superuser, get all clinics
        if request.user.is_superuser:
            clinics = Clinic.objects.all()
        else:
            # For regular users, get only their assigned clinic
            if hasattr(request.user, 'profile') and request.user.profile.clinic:
                clinics = [request.user.profile.clinic]
            else:
                clinics = []

        clinic_data = []
        for clinic in clinics:
            clinic_data.append({
                'id': clinic.id,
                'name': clinic.name,
                'email': clinic.email,
                'phone_number': clinic.phone_number,
                'registration_number': clinic.registration_number,
            })

        print(f"Returning {len(clinic_data)} clinics") # Debug log
        return Response(clinic_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Get clinics API error: {str(e)}")  # Debug log
        return Response({
            'error': 'Failed to fetch clinics',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def edit_doctor_api(request, doctor_id):
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        
        if request.method == 'GET':
            data = {
                'id': doctor.id,
                'name': doctor.name,
                'email': doctor.email,
                'phone_number': doctor.phone_number,
                'address': doctor.address,
                'pincode': doctor.pincode,
                'is_active': doctor.is_active
            }
            return Response(data, status=status.HTTP_200_OK)
            
        elif request.method == 'PUT':
            # Update only allowed fields
            doctor.email = request.data.get('email', doctor.email)
            doctor.phone_number = request.data.get('phone_number', doctor.phone_number)
            doctor.address = request.data.get('address', doctor.address)
            doctor.pincode = request.data.get('pincode', doctor.pincode)
            doctor.save()
            
            return Response({'message': 'Doctor updated successfully'}, status=status.HTTP_200_OK)
            
    except Exception as e:
        print(f"Edit doctor error: {str(e)}")  # Debug print
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def doctor_detail_api(request, doctor_id):
    """API endpoint to get and update doctor details"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        
        if request.method == 'GET':
            # Return doctor details
            return Response({
                'id': doctor.id,
                'name': doctor.name,
                'email': doctor.email,
                'phone_number': doctor.phone_number,
                'address': doctor.address,
                'pincode': doctor.pincode,
                'is_active': doctor.is_active,
                'specialization': doctor.specialization,
                'license_number': doctor.license_number
            }, status=status.HTTP_200_OK)
            
        elif request.method == 'PUT':
            # Update doctor details
            for field in ['email', 'phone_number', 'address', 'pincode']:
                if field in request.data:
                    setattr(doctor, field, request.data[field])
            doctor.save()
            
            return Response({
                'message': 'Doctor updated successfully'
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        print(f"Doctor detail API error: {str(e)}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_status_api(request, doctor_id):
    """API endpoint to get and update doctor status"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        
        if request.method == 'POST':
            is_active = request.data.get('is_active')
            if is_active is not None:  # Check if value was provided
                doctor.is_active = is_active
                doctor.save()
                return Response({'message': 'Doctor status updated successfully'}, status=status.HTTP_200_OK)
            return Response({'error': 'is_active field is required'}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"Status update error: {str(e)}")  # Debug log
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_clinic(request):
    """API endpoint to get current clinic"""
    try:
        if request.user.is_superuser:
            # For superuser, get from session or first clinic
            clinic_id = request.session.get('current_clinic_id')
            if not clinic_id:
                clinic = Clinic.objects.first()
                clinic_id = clinic.id if clinic else None
        else:
            # For regular users, get their assigned clinic
            clinic_id = request.user.profile.clinic.id if hasattr(request.user, 'profile') and request.user.profile.clinic else None

        return Response({
            'clinic_id': clinic_id,
            'success': True
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Get current clinic error: {str(e)}")
        return Response({
            'error': 'Failed to fetch current clinic',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
@user_passes_test(lambda u: u.is_staff)
def add_lab(request):
    """Add a new lab to the clinic"""
    try:
        # Get the clinic from user's profile
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            clinic = request.user.profile.clinic
            
        if request.method == 'POST':
            form = LabForm(request.POST)
            if form.is_valid():
                lab = form.save(commit=False)
                lab.clinic = clinic
                lab.save()
                messages.success(request, 'Lab added successfully.')
                return redirect('users:labs_list')
        else:
            form = LabForm()
        
        return render(request, 'clinic_admin/add_lab.html', {
            'form': form,
            'title': 'Add New Lab',
            'clinic': clinic
        })
    except Exception as e:
        messages.error(request, f'Error adding lab: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@user_passes_test(lambda u: u.is_staff)
def labs_list(request):
    """Display list of labs"""
    try:
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            clinic = request.user.profile.clinic
            
        labs = Lab.objects.filter(clinic=clinic)
        return render(request, 'clinic_admin/labs_list.html', {
            'labs': labs,
            'title': 'Labs Management',
            'clinic': clinic
        })
    except Exception as e:
        messages.error(request, f'Error accessing labs: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@user_passes_test(lambda u: u.is_staff)
def lab_staff_list(request):
    """Display list of lab staff"""
    try:
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            clinic = request.user.profile.clinic
            
        lab_staff = LabStaff.objects.filter(lab__clinic=clinic)
        return render(request, 'clinic_admin/lab_staff_list.html', {
            'lab_staff': lab_staff,
            'title': 'Lab Staff Management',
            'clinic': clinic
        })
    except Exception as e:
        messages.error(request, f'Error accessing lab staff: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@user_passes_test(lambda u: u.is_staff)
def lab_tests(request):
    """Display list of lab tests"""
    try:
        if request.user.is_superuser:
            clinic_id = request.session.get('current_clinic_id')
            clinic = get_object_or_404(Clinic, id=clinic_id)
        else:
            clinic = request.user.profile.clinic
            
        tests = LabTest.objects.filter(prescription__doctor__clinic=clinic).order_by('-created_at')
        return render(request, 'clinic_admin/lab_tests.html', {
            'tests': tests,
            'title': 'Lab Tests',
            'clinic': clinic
        })
    except Exception as e:
        messages.error(request, f'Error accessing lab tests: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@require_POST
def assign_doctor(request):
    """Assign an existing doctor to the current clinic"""
    try:
        doctor_id = request.POST.get('doctor')
        if not doctor_id:
            return JsonResponse({'error': 'Doctor ID is required'}, status=400)
            
        # Get current clinic
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
        else:
            current_clinic_id = request.user.profile.clinic.id
            
        if not current_clinic_id:
            return JsonResponse({'error': 'No clinic selected'}, status=400)
            
        doctor = get_object_or_404(Doctor, id=doctor_id)
        clinic = get_object_or_404(Clinic, id=current_clinic_id)
        
        # Check if doctor is already assigned to this clinic
        if doctor.clinic == clinic:
            return JsonResponse({'error': 'Doctor is already assigned to this clinic'}, status=400)
            
        # Assign doctor to clinic
        doctor.clinic = clinic
        doctor.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_doctors(request):
    """Get list of doctors not assigned to any clinic"""
    try:
        # Get current clinic
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
        else:
            current_clinic_id = request.user.profile.clinic.id
            
        # Get doctors not assigned to any clinic
        doctors = Doctor.objects.filter(clinic__isnull=True)
        
        doctor_data = []
        for doctor in doctors:
            doctor_data.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'email': doctor.email
            })
            
        return Response(doctor_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@login_required
@user_is_admin
def staff_leaves(request):
    """View for managing staff leave requests"""
    try:
        clinic = request.user.clinic_admin.clinic
        leave_requests = StaffLeave.objects.filter(
            staff__clinic=clinic
        ).order_by('-created_at')
        
        total_requests = leave_requests.count()
        pending_requests = leave_requests.filter(status='pending').count()
        approved_requests = leave_requests.filter(status='approved').count()
        
        context = {
            'leave_requests': leave_requests,
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
        }
        
        return render(request, 'clinic_admin/staff_leaves.html', context)
        
    except Exception as e:
        messages.error(request, f'Error accessing staff leaves: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@user_is_admin
def approve_staff_leave(request, leave_id):
    """Approve a staff leave request"""
    try:
        leave = StaffLeave.objects.get(id=leave_id)
        if leave.staff.clinic != request.user.clinic_admin.clinic:
            raise PermissionDenied("You don't have permission to approve this leave request")
            
        leave.status = 'approved'
        leave.save()
        
        # Notify staff member
        Notification.objects.create(
            user=leave.staff.user,
            title='Leave Request Approved',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been approved',
            notification_type='leave_approval'
        )
        
        messages.success(request, 'Leave request approved successfully')
        
    except Exception as e:
        messages.error(request, f'Error approving leave request: {str(e)}')
        
    return redirect('users:staff_leaves')

@login_required
@user_is_admin
def reject_staff_leave(request, leave_id):
    """Reject a staff leave request"""
    try:
        leave = StaffLeave.objects.get(id=leave_id)
        if leave.staff.clinic != request.user.clinic_admin.clinic:
            raise PermissionDenied("You don't have permission to reject this leave request")
            
        leave.status = 'rejected'
        leave.save()
        
        # Notify staff member
        Notification.objects.create(
            user=leave.staff.user,
            title='Leave Request Rejected',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been rejected',
            notification_type='leave_rejection'
        )
        
        messages.success(request, 'Leave request rejected successfully')
        
    except Exception as e:
        messages.error(request, f'Error rejecting leave request: {str(e)}')
        
    return redirect('users:staff_leaves')

@login_required
@user_is_admin
def doctor_leaves(request):
    """View for managing doctor leave requests"""
    try:
        if request.user.is_superuser:
            # Get current clinic from session or default to first clinic
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            
            if current_clinic_id:
                current_clinic = Clinic.objects.get(id=current_clinic_id)
                leave_requests = DoctorLeave.objects.filter(
                    doctor__clinic=current_clinic
                ).order_by('-created_at')
                
                # Get all clinics for superuser
                clinic_list = Clinic.objects.all()
                
                # Handle clinic change
                if request.method == 'POST' and 'clinic_id' in request.POST:
                    new_clinic_id = request.POST.get('clinic_id')
                    if new_clinic_id:
                        request.session['current_clinic_id'] = new_clinic_id
                        return redirect('users:doctor_leaves')
                    
                # Handle clinic assignment
                if request.method == 'POST' and 'assign_clinic' in request.POST:
                    doctor_id = request.POST.get('doctor_id')
                    new_clinic_id = request.POST.get('assign_clinic')
                    if doctor_id and new_clinic_id:
                        doctor = Doctor.objects.get(id=doctor_id)
                        new_clinic = Clinic.objects.get(id=new_clinic_id)
                        doctor.clinic = new_clinic
                        doctor.save()
                        messages.success(request, f'Doctor assigned to {new_clinic.name} successfully')
                        return redirect('users:doctor_leaves')
            else:
                leave_requests = DoctorLeave.objects.none()
                
            # Get all clinics for superuser
            clinic_list = Clinic.objects.all()
            
            # Handle clinic change
            if request.method == 'POST' and 'clinic_id' in request.POST:
                new_clinic_id = request.POST.get('clinic_id')
                if new_clinic_id:
                    request.session['current_clinic_id'] = new_clinic_id
                    return redirect('users:doctor_leaves')
                    
            # Handle clinic assignment
            if request.method == 'POST' and 'assign_clinic' in request.POST:
                doctor_id = request.POST.get('doctor_id')
                new_clinic_id = request.POST.get('assign_clinic')
                if doctor_id and new_clinic_id:
                    doctor = Doctor.objects.get(id=doctor_id)
                    new_clinic = Clinic.objects.get(id=new_clinic_id)
                    doctor.clinic = new_clinic
                    doctor.save()
                    messages.success(request, f'Doctor assigned to {new_clinic.name} successfully')
                    return redirect('users:doctor_leaves')
        else:
            # Non-superuser sees their assigned clinic
            current_clinic = request.user.clinic_admin.clinic
            leave_requests = DoctorLeave.objects.filter(
                doctor__clinic=current_clinic
            ).order_by('-created_at')
            clinic_list = None
        
        total_requests = leave_requests.count()
        pending_requests = leave_requests.filter(status='pending').count()
        approved_requests = leave_requests.filter(status='approved').count()
        
        context = {
            'leave_requests': leave_requests,
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
            'current_clinic': current_clinic if 'current_clinic' in locals() else None,
            'clinic_list': clinic_list,
            'all_clinics': Clinic.objects.all() if request.user.is_superuser else None
        }
        
        return render(request, 'clinic_admin/doctor_leaves.html', context)
        
    except Exception as e:
        messages.error(request, f'Error accessing doctor leaves: {str(e)}')
        return redirect('users:clinic_admin_dashboard')

@login_required
@user_is_admin
def approve_doctor_leave(request, leave_id):
    """Approve a doctor leave request"""
    try:
        leave = DoctorLeave.objects.get(id=leave_id)
        
        # Check clinic permission
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            if leave.doctor.clinic.id != current_clinic_id:
                raise PermissionDenied("You don't have permission to approve this leave request")
        else:
            if leave.doctor.clinic != request.user.clinic_admin.clinic:
                raise PermissionDenied("You don't have permission to approve this leave request")
            
        # Update status and save
        leave.status = 'approved'
        leave.save()
        
        # Notify doctor
        Notification.objects.create(
            user=leave.doctor.user,
            title='Leave Request Approved',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been approved',
            notification_type='leave_approval'
        )
        
        messages.success(request, 'Leave request approved successfully')
        
    except Exception as e:
        messages.error(request, f'Error approving leave request: {str(e)}')
        
    return redirect('users:doctor_leaves')

@login_required
@user_is_admin
def reject_doctor_leave(request, leave_id):
    """Reject a doctor leave request"""
    try:
        leave = DoctorLeave.objects.get(id=leave_id)
        
        # Check clinic permission
        if request.user.is_superuser:
            current_clinic_id = request.session.get('current_clinic_id')
            if not current_clinic_id:
                first_clinic = Clinic.objects.first()
                if first_clinic:
                    current_clinic_id = first_clinic.id
                    request.session['current_clinic_id'] = current_clinic_id
            if leave.doctor.clinic.id != current_clinic_id:
                raise PermissionDenied("You don't have permission to reject this leave request")
        else:
            if leave.doctor.clinic != request.user.clinic_admin.clinic:
                raise PermissionDenied("You don't have permission to reject this leave request")
            
        leave.status = 'rejected'
        leave.save()
        
        # Notify doctor
        Notification.objects.create(
            user=leave.doctor.user,
            title='Leave Request Rejected',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been rejected',
            notification_type='leave_rejection'
        )
        
        messages.success(request, 'Leave request rejected successfully')
        
    except Exception as e:
        messages.error(request, f'Error rejecting leave request: {str(e)}')
        
    return redirect('users:doctor_leaves')

@login_required
@user_is_admin
def edit_doctor_leave(request, leave_id):
    """Edit a doctor leave request"""
    try:
        leave = DoctorLeave.objects.get(id=leave_id)
        if leave.doctor.clinic != request.user.clinic_admin.clinic:
            raise PermissionDenied("You don't have permission to edit this leave request")
            
        if request.method == 'POST':
            # Update leave details
            leave.start_date = request.POST.get('start_date')
            leave.end_date = request.POST.get('end_date')
            leave.leave_type = request.POST.get('leave_type')
            leave.reason = request.POST.get('reason')
            leave.save()
            
            messages.success(request, 'Leave request updated successfully')
            return redirect('users:doctor_leaves')
            
        context = {
            'leave': leave,
            'leave_types': DoctorLeave.LEAVE_TYPE_CHOICES
        }
        return render(request, 'clinic_admin/edit_doctor_leave.html', context)
        
    except Exception as e:
        messages.error(request, f'Error editing leave request: {str(e)}')
        return redirect('users:doctor_leaves')

@login_required
@user_is_admin
def cancel_doctor_leave(request, leave_id):
    """Cancel a doctor leave request"""
    try:
        leave = DoctorLeave.objects.get(id=leave_id)
        if leave.doctor.clinic != request.user.clinic_admin.clinic:
            raise PermissionDenied("You don't have permission to cancel this leave request")
            
        # Only allow canceling pending requests
        if leave.status != 'pending':
            messages.error(request, 'Only pending leave requests can be canceled')
            return redirect('users:doctor_leaves')
            
        leave.status = 'cancelled'
        leave.save(update_fields=['status'])
        
        # Notify doctor
        Notification.objects.create(
            user=leave.doctor.user,
            title='Leave Request Cancelled',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been cancelled',
            notification_type='leave_cancellation'
        )
        
        messages.success(request, 'Leave request cancelled successfully')
        
    except Exception as e:
        messages.error(request, f'Error cancelling leave request: {str(e)}')
        
    return redirect('users:doctor_leaves')