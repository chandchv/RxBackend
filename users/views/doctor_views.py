from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Doctor, Appointment
from ..serializers import DoctorSerializer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from ..scripts.scrapeGpt01 import verify_doctor as verify_doctor_api
import json
from django.db.models import Q
from datetime import date

class DoctorCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            print("Received data:", request.data)  # Debug print
            
            serializer = DoctorSerializer(data={
                'license_number': request.data.get('license_number'),
                'medical_council': request.data.get('medical_council'),
                'specialization': request.data.get('specialization', ''),
            })
            
            if serializer.is_valid():
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)  # Debug print
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"Error creating doctor: {str(e)}")
            return Response(
                {'error': f'Failed to create doctor profile: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class DoctorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctors = Doctor.objects.all()
        serializer = DoctorSerializer(doctors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DoctorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
            serializer = DoctorSerializer(doctor)
            return Response(serializer.data)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Doctor profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

@login_required
def verify_doctor_api_view(request):
    """API endpoint for doctor verification"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = verify_doctor_api(
                name=data.get('name'),
                registration_number=data.get('registration_number'),
                state_council=data.get('state_council')
            )
            
            return JsonResponse({
                'verified': result.get('verified', False),
                'name': result.get('name'),
                'registration_number': result.get('registration_number'),
                'state_council': result.get('state_council'),
                'qualification': result.get('qualification', ''),
                'registration_date': result.get('registration_date', '')
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'verified': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'verified': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'verified': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def save_doctor(request):
    if request.method == 'POST':
        try:
            verified_data_str = request.POST.get('verified_data', '')
            if not verified_data_str:
                raise ValueError("No verification data provided")

            verified_data = json.loads(verified_data_str)
            print("\nDEBUG: Save Doctor Process")
            print("Received verified data:", verified_data)
            
            # Create or update Doctor record
            doctor, created = Doctor.objects.update_or_create(
                license_number=verified_data.get('registration_number', ''),
                defaults={
                    'name': verified_data.get('name', ''),
                    'medical_council': verified_data.get('state_council', ''),
                    'verified': True,  # Explicitly set to True
                    'specialization': verified_data.get('qualification', ''),
                }
            )
            
            print(f"DEBUG: Doctor {'created' if created else 'updated'}")
            print(f"DEBUG: Doctor details - Name: {doctor.name}, Verified: {doctor.verified}")

            messages.success(request, 'Doctor profile saved successfully!')
            return redirect('users:dashboard')

        except json.JSONDecodeError as e:
            print("JSON Decode Error:", str(e))
            print("Received data:", request.POST.get('verified_data', ''))
            messages.error(request, 'Error processing verification data')
        except Exception as e:
            print("General Error:", str(e))
            messages.error(request, f'Error saving doctor profile: {str(e)}')
        
        return redirect('users:verify_doctor')

    return redirect('users:verify_doctor')

def get_doctors_list(request):
    try:
        doctors = Doctor.objects.all()
        doctors_list = []
        
        for doctor in doctors:
            doctors_list.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization or 'General Practice',
                'medical_council': doctor.medical_council,
                'license_number': doctor.license_number
            })
        
        print(f"Returning {len(doctors_list)} doctors")  # Debug print
        return JsonResponse({'doctors': doctors_list})
    except Exception as e:
        print(f"Error in get_doctors_list: {str(e)}")  # Debug print
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def dashboard_view(request):
    # Get all doctors
    doctors = Doctor.objects.all()
    print(f"Total doctors in database: {doctors.count()}")
    
    # Get today's appointments
    today = date.today()
    today_appointments = Appointment.objects.filter(
        appointment_date__date=today
    ).order_by('appointment_date')
    
    # Format doctors for the template
    formatted_doctors = [
        {
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization or 'General Practice',
            'medical_council': doctor.medical_council,
            'license_number': doctor.license_number
        }
        for doctor in doctors
    ]
    
    context = {
        'doctors': formatted_doctors,
        'today_appointments': today_appointments,
    }
    
    return render(request, 'dashboard.html', context)
