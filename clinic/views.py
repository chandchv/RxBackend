from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from datetime import timedelta
from users.models import Doctor, Patient, Appointment, Staff, Payment
from users.serializers import DoctorSerializer, PatientSerializer, AppointmentSerializer, StaffSerializer
from users.permissions import IsClinicAdmin

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def doctor_list(request):
    try:
        clinic = request.user.clinic
        doctors = Doctor.objects.filter(clinic=clinic)\
            .annotate(
                patient_count=Count('patients', distinct=True),
                appointment_count=Count('appointments', distinct=True)
            )
        
        serializer = DoctorSerializer(doctors, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def update_doctor_status(request, doctor_id):
    try:
        clinic = request.user.clinic
        doctor = Doctor.objects.get(id=doctor_id, clinic=clinic)
        
        status = request.data.get('status')
        if status is not None:
            doctor.is_active = status
            doctor.save()
            
            return Response({
                'message': 'Doctor status updated successfully'
            })
            
        return Response({
            'error': 'Status not provided'
        }, status=400)
        
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def patient_list(request):
    try:
        clinic = request.user.clinic
        patients = Patient.objects.filter(clinic=clinic)\
            .annotate(
                visit_count=Count('appointments', distinct=True)
            )\
            .select_related('assigned_doctor')
        
        serializer = PatientSerializer(patients, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def assign_doctor(request, patient_id):
    try:
        clinic = request.user.clinic
        patient = Patient.objects.get(id=patient_id, clinic=clinic)
        doctor_id = request.data.get('doctor_id')
        
        if not doctor_id:
            return Response({
                'error': 'Doctor ID is required'
            }, status=400)
            
        doctor = Doctor.objects.get(id=doctor_id, clinic=clinic)
        patient.assigned_doctor = doctor
        patient.save()
        
        return Response({
            'message': 'Doctor assigned successfully'
        })
        
    except Patient.DoesNotExist:
        return Response({
            'error': 'Patient not found'
        }, status=404)
    except Doctor.DoesNotExist:
        return Response({
            'error': 'Doctor not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def appointment_list(request):
    try:
        clinic = request.user.clinic
        date = request.GET.get('date')
        status = request.GET.get('status', 'ALL')
        
        appointments = Appointment.objects.filter(clinic=clinic)
        
        # Apply date filter
        if date:
            appointments = appointments.filter(
                appointment_date__date=datetime.strptime(date, '%Y-%m-%d').date()
            )
            
        # Apply status filter
        if status != 'ALL':
            appointments = appointments.filter(status=status)
            
        appointments = appointments.select_related('doctor', 'patient')\
            .order_by('appointment_date')
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def update_appointment_status(request, appointment_id):
    try:
        clinic = request.user.clinic
        appointment = Appointment.objects.get(id=appointment_id, clinic=clinic)
        
        status = request.data.get('status')
        if status not in ['CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW']:
            return Response({
                'error': 'Invalid status'
            }, status=400)
            
        appointment.status = status
        appointment.save()
        
        return Response({
            'message': 'Appointment status updated successfully'
        })
        
    except Appointment.DoesNotExist:
        return Response({
            'error': 'Appointment not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def staff_list(request):
    try:
        clinic = request.user.clinic
        staff = Staff.objects.filter(clinic=clinic)
        serializer = StaffSerializer(staff, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def update_staff_status(request, staff_id):
    try:
        clinic = request.user.clinic
        staff_member = Staff.objects.get(id=staff_id, clinic=clinic)
        
        is_active = request.data.get('is_active')
        if is_active is not None:
            staff_member.is_active = is_active
            staff_member.save()
            
            return Response({
                'message': 'Staff status updated successfully'
            })
            
        return Response({
            'error': 'Status not provided'
        }, status=400)
        
    except Staff.DoesNotExist:
        return Response({
            'error': 'Staff member not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def update_staff_role(request, staff_id):
    try:
        clinic = request.user.clinic
        staff_member = Staff.objects.get(id=staff_id, clinic=clinic)
        
        role = request.data.get('role')
        if role not in ['RECEPTIONIST', 'NURSE', 'ADMIN']:
            return Response({
                'error': 'Invalid role'
            }, status=400)
            
        staff_member.role = role
        staff_member.save()
        
        return Response({
            'message': 'Staff role updated successfully'
        })
        
    except Staff.DoesNotExist:
        return Response({
            'error': 'Staff member not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClinicAdmin])
def clinic_reports(request):
    try:
        # Get clinic based on user's role
        if hasattr(request.user, 'clinic_admin'):
            clinic = request.user.clinic_admin.clinic
        elif hasattr(request.user, 'doctor'):
            clinic = request.user.doctor.clinic
        elif hasattr(request.user, 'staff'):
            clinic = request.user.staff.clinic
        else:
            return Response({
                'error': 'User is not authorized to access clinic reports'
            }, status=400)

        period = request.GET.get('period', 'week')
        today = timezone.now()
        
        # Set time period
        if period == 'week':
            start_date = today - timedelta(days=7)
            date_format = '%a'
        elif period == 'month':
            start_date = today - timedelta(days=30)
            date_format = '%d'
        else:  # year
            start_date = today - timedelta(days=365)
            date_format = '%b'
            
        # Get appointments in period
        appointments = Appointment.objects.filter(
            doctor__clinic=clinic,
            appointment_date__gte=start_date,
            appointment_date__lte=today
        )
        
        # Calculate statistics
        total_appointments = appointments.count()
        completed_appointments = appointments.filter(status='COMPLETED').count()
        completion_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
        
        # Get new patients
        new_patients = Patient.objects.filter(
            doctor__clinic=clinic,
            created_at__gte=start_date,
            created_at__lte=today
        ).count()
        
        # Calculate revenue
        total_revenue = Payment.objects.filter(
            doctor__clinic=clinic,
            created_at__gte=start_date,
            created_at__lte=today
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get appointment trend
        appointment_trend = appointments.extra(
            select={'date': f"DATE_FORMAT(appointment_date, '{date_format}')"}).\
            values('date').annotate(count=Count('id')).order_by('appointment_date')
        
        # Get revenue distribution
        revenue_distribution = Payment.objects.filter(
            doctor__clinic=clinic,
            created_at__gte=start_date,
            created_at__lte=today
        ).values('payment_type').annotate(
            value=Sum('amount'),
            name=F('payment_type')
        )
        
        return Response({
            'totalAppointments': total_appointments,
            'totalRevenue': total_revenue,
            'newPatients': new_patients,
            'completionRate': round(completion_rate, 1),
            'appointmentTrend': {
                'labels': [item['date'] for item in appointment_trend],
                'data': [item['count'] for item in appointment_trend]
            },
            'revenueDistribution': revenue_distribution,
            'performanceSummary': [
                {'label': 'Average Daily Appointments', 'value': round(total_appointments / 7, 1)},
                {'label': 'Completion Rate', 'value': f"{round(completion_rate, 1)}%"},
                {'label': 'Average Revenue per Patient', 'value': f"${round(total_revenue/total_appointments, 2) if total_appointments > 0 else 0}"}
            ]
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=400) 