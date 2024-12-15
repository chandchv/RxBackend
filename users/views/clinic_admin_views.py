from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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

@login_required
def clinic_admin_dashboard(request):
    """Main clinic administration dashboard view"""
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to access the admin panel.")
        return redirect('users:dashboard')
        
    today = timezone.now().date()
    
    context = {
        'doctors_count': Doctor.objects.count(),
        'staff_count': Staff.objects.count(),
        # Remove or comment out the patients count for now
        # 'patients_count': Patient.objects.count(),
        # Remove appointments count as well if Appointment model doesn't exist
        # 'todays_appointments': Appointment.objects.filter(
        #     appointment_date__date=today
        # ).count(),
    }
    
    return render(request, 'clinic_admin/admin_dashboard.html', context)

@login_required
def clinic_profile(request):
    """View and update clinic profile"""
    user_profile = request.user.userprofile
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
    clinic = request.user.userprofile.clinic
    
    if not clinic:
        messages.error(request, "Please set up your clinic first.")
        return redirect('users:clinic_profile')
        
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
            
            messages.success(request, f'Doctor added successfully! Initial password: {random_password}')
            return redirect('users:doctors_list')
            
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
    clinic = request.user.userprofile.clinic
    
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
        #from ..scripts.scrapeGpt1 import verify_doctor as verify_doctor_api
        success, result = verify_doctor_api(doctor_details)
        
        print("\n=== Verification Response ===")
        print(f"Success: {success}")
        print(f"Result: {result}")
        
        if success and isinstance(result, dict):
            return JsonResponse({
                'verified': True,
                'verification_data': {
                    'name': result.get('name', ''),
                    'father_name': result.get('father_name', ''),
                    'date_of_birth': result.get('date_of_birth', ''),
                    'registration_number': result.get('registration_number', ''),
                    'registration_date': result.get('registration_date', ''),
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