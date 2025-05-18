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
from rest_framework.decorators import api_view, permission_classes
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from notifications.utils import create_notification

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
def appointment_detail(request, pk):
    """View for showing appointment details"""
    appointment = get_object_or_404(Appointment, id=pk)
    
    # Check permissions
    if not (request.user.is_staff or request.user == appointment.doctor.user or 
            request.user == appointment.patient.user):
        return HttpResponse("Permission denied", status=403)
    
    context = {
        'appointment': appointment,
        'patient': appointment.patient,
    }
    
    # If it's an HTMX request, return the modal template
    if request.headers.get('HX-Request'):
        return render(request, 'appointment_detail_modal.html', context)
    
    # For regular requests, use the full page template
    if hasattr(request.user, 'patient'):
        return render(request, 'patient/appointment_detail.html', context)
    elif hasattr(request.user, 'doctor'):
        return render(request, 'doctor/appointment_detail.html', context)
    else:
        return render(request, 'staff/appointment_detail.html', context)

@login_required
def appointment_delete(request, appointment_id):
    """Delete an appointment"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions
    if not (request.user.is_staff or request.user == appointment.doctor.user):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    if request.method == 'POST':
        appointment.delete()
        return JsonResponse({"status": "success"})
    
    return JsonResponse({"error": "Invalid request"}, status=400)

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
                
                # --- Add Notifications --- 
                try:
                    # Notify Doctor
                    create_notification(
                        recipient=appointment.doctor.user,
                        message=f"New appointment scheduled with {appointment.patient.get_full_name()} on {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}.",
                        sender=request.user, # The admin/staff who created it
                        notification_type='appointment_new',
                        related_object=appointment
                    )
                    # Notify Patient
                    create_notification(
                        recipient=appointment.patient.user,
                        message=f"Your appointment with Dr. {appointment.doctor.name} is scheduled for {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}.",
                        sender=request.user,
                        notification_type='appointment_new',
                        related_object=appointment
                    )
                except Exception as e:
                    print(f"Error creating notification in admin_create_appointment: {e}")
                    # Optionally add a message, but don't break the flow
                    messages.warning(request, "Appointment created, but failed to send notifications.")
                # --- End Notifications ---
                
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
@csrf_exempt
@require_POST
def update_appointment_status(request, appointment_id):
    """Update appointment status"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # Check permissions
        if not (request.user.is_staff or request.user == appointment.doctor.user):
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        # Parse JSON data from request body
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
        except json.JSONDecodeError:
            new_status = request.POST.get('status')
            
        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
            appointment.save()
            
            # Create notification for patient
            try:
                create_notification(
                    recipient=appointment.patient.user,
                    message=f"Your appointment with Dr. {appointment.doctor.name} has been marked as {new_status}.",
                    notification_type='appointment_status_update',
                    sender=request.user,
                    related_object=appointment,
                    action_url=f'/appointments/{appointment.id}/detail/'
                )
            except Exception as e:
                print(f"Error creating notification: {str(e)}")
            
            return JsonResponse({
                "status": "success",
                "new_status": new_status,
                "message": f"Appointment marked as {new_status}"
            })
        
        return JsonResponse({"error": "Invalid status"}, status=400)
        
    except Exception as e:
        print(f"Error updating appointment status: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def appointment_edit(request, appointment_id):
    """Edit an appointment"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # Check permissions
        if not (request.user.is_staff or request.user == appointment.doctor.user):
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                appointment.appointment_date = data.get('appointment_date')
                appointment.appointment_time = data.get('appointment_time')
                appointment.reason = data.get('reason')
                appointment.save()
                
                # Create notification for patient
                try:
                    create_notification(
                        recipient=appointment.patient.user,
                        message=f"Your appointment with Dr. {appointment.doctor.name} has been rescheduled to {appointment.appointment_date.strftime('%d-%b-%Y')} at {appointment.appointment_time.strftime('%I:%M %p')}.",
                        sender=request.user,
                        notification_type='appointment_rescheduled',
                        related_object=appointment
                    )
                except Exception as e:
                    print(f"Error creating notification: {str(e)}")
                
                return JsonResponse({
                    "status": "success",
                    "message": "Appointment updated successfully",
                    "redirect_url": request.META.get('HTTP_REFERER', '/') 
                })
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON data"}, status=400)
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)
        
        context = {
            'appointment': appointment,
            'min_date': timezone.now().date(),
        }
        
        if request.headers.get('HX-Request'):
            return render(request, 'appointment_edit_modal.html', context)
        return render(request, 'appointment_edit.html', context)
        
    except Exception as e:
        print(f"Error in appointment_edit: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

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
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_appointment_status_api(request, appointment_id):
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.data.get('status')
        
        # Verify the user has permission to update this appointment
        if not hasattr(request.user, 'doctor') or request.user.doctor != appointment.doctor:
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=403)
            
        if new_status not in dict(Appointment.STATUS_CHOICES):
            return Response({
                'success': False,
                'message': 'Invalid status'
            }, status=400)
            
        # Update the appointment status
        appointment.status = new_status
        appointment.save()
        
        # Send notification to patient
        try:
            # --- Add Notification --- 
            create_notification(
                recipient=appointment.patient.user,
                message=f"Your appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date.strftime('%d-%b-%Y')} has been updated to: {new_status.capitalize()}.",
                sender=request.user,
                notification_type='appointment_status_update',
                related_object=appointment
            )
            # --- End Notification ---
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
        
        return Response({
            'success': True,
            'message': f'Appointment marked as {new_status}',
            'new_status': new_status
        })
        
    except Exception as e:
        print(f"Error updating appointment status: {str(e)}")
        return Response({
            'success': False,
            'message': 'Error updating appointment status'
        }, status=500)