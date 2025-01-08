from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import Appointment, Patient, Doctor, DoctorAvailability
from ..serializers import AppointmentSerializer
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from users.forms import AppointmentForm
from django.contrib import messages
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_http_methods

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
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@login_required
def appointments_view(request):
    """Main appointments page view"""
    clinic = request.user.profile.clinic
    appointments = Appointment.objects.filter(doctor__clinic=clinic)
    patients = Patient.objects.filter(clinic=clinic)
    return render(request, 'appointments.html', {
        'appointments': appointments, 
        'patients': patients
    })

@login_required
def create_appointment(request):
    clinic = request.user.userprofile.clinic
    patients = Patient.objects.filter(clinic=clinic)
    
    if request.method == 'POST':
        try:
            appointment = Appointment.objects.create(
                patient_id=request.POST['patient'],
                doctor=request.user.doctor,
                appointment_date=datetime.strptime(
                    f"{request.POST['appointment_date']} {request.POST['appointment_time']}", 
                    "%Y-%m-%d %H:%M"
                ),
                reason=request.POST.get('reason', ''),
                status='scheduled'
            )
            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('users:patient_dashboard')
        except Exception as e:
            messages.error(request, f'Error scheduling appointment: {str(e)}')
    
    return render(request, 'appointments/create_appointment.html', {
        'patients': patients
    }) 

@login_required
def appointment_detail(request, appointment_id):
    """View for showing appointment details in a modal"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions
    if not (request.user.is_staff or request.user == appointment.doctor.user or 
            request.user == appointment.patient.user):
        return HttpResponse("Permission denied", status=403)
    
    context = {
        'appointment': appointment,
    }
    return render(request, 'appointment_detail_modal.html', context)

@login_required
def appointment_delete(request, appointment_id):
    """View for deleting/canceling appointments"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # Check permissions
        if not (request.user.is_staff or request.user == appointment.doctor.user or 
                request.user == appointment.patient.user):
            return HttpResponse("Permission denied", status=403)
        
        # Mark as cancelled instead of deleting
        appointment.status = 'cancelled'
        appointment.save()
        
        # If it's an HTMX request, return updated row
        if request.headers.get('HX-Request'):
            return render(request, 'appointment_row.html', {'appointment': appointment})
        
        messages.success(request, 'Appointment cancelled successfully')
        return redirect('users:appointments_list')
        
    except Exception as e:
        print(f"Error cancelling appointment: {str(e)}")
        return HttpResponse("Error cancelling appointment", status=500)

@login_required
def admin_create_appointment(request):
    try:
        # Verify user is clinic admin
        if not request.user.is_staff:
            messages.error(request, 'Access denied. Staff only.')
            return redirect('users:dashboard')
            
        if request.method == 'POST':
            doctor_id = request.POST.get('doctor')
            patient_id = request.POST.get('patient')
            appointment_date = request.POST.get('appointment_date')
            appointment_time = request.POST.get('appointment_time')
            reason = request.POST.get('reason', '')
            
            # Validate required fields
            if not all([doctor_id, patient_id, appointment_date, appointment_time]):
                messages.error(request, 'Please fill all required fields.')
                return redirect('users:admin_create_appointment')
                
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                patient = Patient.objects.get(id=patient_id)
                
                # Create appointment
                appointment = Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reason=reason,
                    status='scheduled'
                )
                
                # Send notifications
                send_appointment_notifications(appointment)
                
                messages.success(request, 'Appointment scheduled successfully!')
                return redirect('users:clinic_admin_dashboard')
                
            except (Doctor.DoesNotExist, Patient.DoesNotExist):
                messages.error(request, 'Invalid doctor or patient selected.')
                
        # GET request - show form
        context = {
            'doctors': Doctor.objects.all(),
            'patients': Patient.objects.all()
        }
        return render(request, 'clinic_admin/create_appointment.html', context)
        
    except Exception as e:
        print(f"Error in admin_create_appointment: {str(e)}")
        messages.error(request, 'Error creating appointment.')
        return redirect('users:clinic_admin_dashboard')

def send_appointment_notifications(appointment):
    """Send notifications to doctor and patient about the appointment"""
    try:
        # Email notifications
        send_mail(
            subject='New Appointment Scheduled',
            message=f'An appointment has been scheduled for {appointment.appointment_date} at {appointment.appointment_time}',
            from_email='your@email.com',
            recipient_list=[appointment.doctor.user.email, appointment.patient.user.email],
            fail_silently=False,
        )
        
        # SMS notifications (using Twilio or similar service)
        if appointment.doctor.phone:
            send_sms(
                to=appointment.doctor.phone,
                message=f'New appointment scheduled with {appointment.patient.get_full_name()} on {appointment.appointment_date} at {appointment.appointment_time}'
            )
            
        if appointment.patient.phone:
            send_sms(
                to=appointment.patient.phone,
                message=f'Your appointment with Dr. {appointment.doctor.get_full_name()} is scheduled for {appointment.appointment_date} at {appointment.appointment_time}'
            )
            
    except Exception as e:
        print(f"Error sending notifications: {str(e)}")

@login_required
@require_POST
def update_appointment_status(request, appointment_id):
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.POST.get('status')
        
        # Verify the user has permission to update this appointment
        if request.user.doctor != appointment.doctor and not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'message': 'Permission denied'
            }, status=403)
            
        if new_status not in dict(Appointment.STATUS_CHOICES):
            return JsonResponse({
                'success': False,
                'message': 'Invalid status'
            }, status=400)
            
        # Update the appointment status
        appointment.status = new_status
        appointment.save()
        
        # Send notification to patient
        try:
            send_status_update_notification(appointment)
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'Appointment marked as {new_status}',
            'new_status': new_status
        })
        
    except Exception as e:
        print(f"Error updating appointment status: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error updating appointment status'
        }, status=500)

@login_required
def appointment_edit(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions
    if not (request.user.is_staff or request.user == appointment.doctor.user):
        messages.error(request, 'Permission denied')
        return HttpResponse("Permission denied", status=403)
    
    if request.method == 'POST':
        try:
            # Get form data
            new_date = request.POST.get('appointment_date')
            new_time = request.POST.get('appointment_time')
            new_reason = request.POST.get('reason')
            
            # Update appointment
            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.reason = new_reason
            appointment.save()
            
            # Send notification
            try:
                send_appointment_update_notification(appointment)
            except Exception as e:
                print(f"Error sending notification: {str(e)}")
            
            messages.success(request, 'Appointment updated successfully')
            
            # If it's an HTMX request, return the updated row
            if request.headers.get('HX-Request'):
                return render(request, 'appointment_row.html', {'appointment': appointment})
            return redirect('users:appointments_list')
            
        except Exception as e:
            print(f"Error updating appointment: {str(e)}")
            messages.error(request, 'Error updating appointment')
            return HttpResponse("Error updating appointment", status=500)
    
    # Render edit form
    return render(request, 'appointment_edit_modal.html', {'appointment': appointment})

@login_required
@require_http_methods(["GET"])
def get_available_slots(request, doctor_id, date):
    """API endpoint to get available slots for a doctor on a specific date"""
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()  # Convert to date object
        
        # Get doctor's availability for the selected day
        day_of_week = selected_date.weekday()
        availability = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_available=True
        ).first()
        
        if not availability:
            return JsonResponse({
                'slots': [],
                'message': 'Doctor not available on this day'
            })
        
        # Get booked appointments
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,  # Use date object here
            status='scheduled'
        ).values_list('appointment_time', flat=True)
        
        # Generate available slots
        available_slots = []
        current_time = datetime.combine(selected_date, availability.start_time)
        end_time = datetime.combine(selected_date, availability.end_time)
        
        while current_time < end_time:
            slot_time = current_time.time()
            if slot_time not in booked_slots:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M'),
                    'available': True
                })
            current_time += timedelta(minutes=30)
        
        return JsonResponse({
            'slots': available_slots,
            'doctor_name': doctor.name,
            'date': date
        })
        
    except Exception as e:
        print(f"Error generating slots: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@api_view(['GET'])
def get_doctor_slots(request, doctor_id, date):
    try:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get doctor's availability for the selected day
        day_of_week = selected_date.weekday()
        availability = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_available=True
        ).first()
        
        if not availability:
            return Response({
                'slots': [],
                'message': 'Doctor not available on this day'
            })
            
        # Get booked appointments
        booked_slots = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status='scheduled'
        ).values_list('appointment_time', flat=True)
        
        # Generate available slots
        available_slots = []
        current_time = datetime.combine(selected_date, availability.start_time)
        end_time = datetime.combine(selected_date, availability.end_time)
        
        while current_time < end_time:
            slot_time = current_time.time()
            if slot_time not in booked_slots:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M'),
                    'available': True
                })
            current_time += timedelta(minutes=30)  # 30-minute slots
            
        return Response({
            'slots': available_slots,
            'doctor_name': doctor.name,
            'date': date
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)
