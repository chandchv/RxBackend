from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponse
from ..models import Patient, Appointment, UserProfile
from ..scripts import scrapeGpt01 as scrapper
from django.contrib.auth.models import User
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse



def signup_view(request):
    if request.method == 'POST':
        # Handle form submission
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.create_user(username=username, 
                                          email=email, 
                                          password=password)
            profile = UserProfile.objects.create(user=user)
            login(request, user)
            return redirect('dashboard_view')
        except Exception as e:
            return render(request, 'signup.html', {'error': str(e)})
    
    return render(request, 'signup.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            return redirect('users:dashboard')
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')
    

@login_required
def appointments_list(request):
    """View for HTMX to load appointments list"""
    appointments = Appointment.objects.filter(doctor=request.user).order_by('-date')
    return render(request, 'appointments_list.html', {
        'appointments': appointments
    })

@login_required
def appointments_view(request):
    """Main appointments page view"""
    context = {
        'patients': Patient.objects.all()
    }
    return render(request, 'appointments.html', context)

@login_required
def profile_view(request):
    profile = request.user.userprofile
    return render(request, 'profile.html', {'profile': profile})

@login_required
def profile_edit_view(request):
    profile = request.user.userprofile
    if request.method == 'POST':
        # Handle profile update
        profile.phone_number = request.POST.get('phone_number')
        profile.address = request.POST.get('address')
        profile.pincode = request.POST.get('pincode')
        profile.medical_degree = request.POST.get('medical_degree')
        profile.license_number = request.POST.get('license_number')
        profile.state_council = request.POST.get('state_council')
        profile.save()
        
        # Update user information
        user = request.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        
        return redirect('profile')
    
    return render(request, 'profile_edit.html', {'profile': profile})

def logout_view(request):
    logout(request)
    return redirect('users:login')

@login_required
def appointment_detail(request, pk):
    """View for individual appointment details"""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    return render(request, 'appointment_detail.html', {
        'appointment': appointment
    })

@login_required
def appointment_delete(request, pk):
    """View for deleting appointments via HTMX"""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    if request.method == 'DELETE':
        appointment.delete()
        return HttpResponse(status=204)
    return HttpResponse(status=405)

@login_required(login_url='users:login')
def patients_view(request):
    """Main patients listing page"""
    patients = Patient.objects.all()
    return render(request, 'patients.html', {'patients': patients})

@login_required
def patient_detail(request, pk):
    """View for individual patient details"""
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, 'patient_detail.html', {'patient': patient})

@login_required
def patient_edit(request, pk):
    """View for editing patient details"""
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        # Handle patient update
        patient.first_name = request.POST.get('first_name')
        patient.last_name = request.POST.get('last_name')
        patient.email = request.POST.get('email')
        patient.phone_number = request.POST.get('phone_number')
        patient.save()
        return redirect('patient_detail', pk=pk)
    return render(request, 'patient_edit.html', {'patient': patient})

@login_required
def patient_form(request):
    """Handle patient form view"""
    return render(request, 'patients/create_patient.html')

@login_required
def patient_list(request):
    """Handle patient list view"""
    return render(request, 'patients/patient_list.html')

@login_required(login_url='users:login')
def create_patient(request):
    if request.method == 'POST':
        try:
            patient = Patient.objects.create(
                patient_id=request.POST.get('patient_id'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                date_of_birth=request.POST.get('date_of_birth'),
                gender=request.POST.get('gender'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email'),
                address=request.POST.get('address'),
                pincode=request.POST.get('pincode')
            )
            # If using HTMX, return a success message
            return HttpResponse(
                '<div class="text-green-500">Patient created successfully!</div>',
                headers={'HX-Redirect': reverse('users:patients_list')}
            )
        except Exception as e:
            # If using HTMX, return an error message
            return HttpResponse(
                f'<div class="text-red-500">Error creating patient: {str(e)}</div>',
                status=400
            )
    return render(request, 'patient_form.html') 