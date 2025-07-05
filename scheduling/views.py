from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.views.decorators.http import require_POST
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from users.models import Doctor, Patient, Clinic, Appointment
from .models import AppointmentSchedule, AppointmentType, Holiday, ScheduledAppointment, SchedulingSettings
from .forms import AppointmentForm, AppointmentScheduleForm, HolidayForm
from django.shortcuts import redirect, get_object_or_404

def login_view(request):
    if request.user.is_authenticated:
        return redirect('scheduling:dashboard')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Get user role for message
                user_role = "User"
                if hasattr(user, 'doctor'):
                    user_role = "Doctor"
                elif user.is_superuser:
                    user_role = "Administrator"
                elif user.is_staff:
                    user_role = "Staff"
                
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}! You are logged in as {user_role}.")
                next_url = request.POST.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect('scheduling:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'scheduling/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('scheduling:login')

class AppointmentListView(LoginRequiredMixin, ListView):
    model = Appointment  # Use users.Appointment as primary model
    template_name = 'scheduling/appointment_list.html'
    context_object_name = 'appointments'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            queryset = queryset.filter(appointment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(appointment_date__lte=end_date)
            
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        # Filter by other parameters
        doctor_id = self.request.GET.get('doctor')
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
            
        # If user is a doctor, show only their appointments
        if hasattr(self.request.user, 'doctor'):
            queryset = queryset.filter(doctor=self.request.user.doctor)
            
        return queryset.order_by('-appointment_date', 'appointment_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doctors'] = Doctor.objects.all()
        context['statuses'] = Appointment.STATUS_CHOICES
        
        # Add filters to context
        context['filters'] = {
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
            'status': self.request.GET.get('status', ''),
            'doctor': self.request.GET.get('doctor', ''),
        }
        return context

class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model = Appointment  # Use users.Appointment
    template_name = 'scheduling/appointment_detail.html'
    context_object_name = 'appointment'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get scheduling info if it exists
        try:
            context['scheduling_info'] = ScheduledAppointment.objects.get(appointment=self.object)
        except ScheduledAppointment.DoesNotExist:
            context['scheduling_info'] = None
        return context

class AppointmentCreateView(LoginRequiredMixin, CreateView):
    model = Appointment  # Use users.Appointment
    form_class = AppointmentForm
    template_name = 'scheduling/appointment_form.html'
    success_url = reverse_lazy('scheduling:appointment_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment created successfully.')
        return super().form_valid(form)

class AppointmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Appointment  # Use users.Appointment
    form_class = AppointmentForm
    template_name = 'scheduling/appointment_form.html'
    success_url = reverse_lazy('scheduling:appointment_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment updated successfully.')
        return super().form_valid(form)

class AppointmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Appointment  # Use users.Appointment
    template_name = 'scheduling/appointment_confirm_delete.html'
    success_url = reverse_lazy('scheduling:appointment_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Appointment deleted successfully.')
        return super().delete(request, *args, **kwargs)

@login_required
def appointment_calendar(request):
    """Display appointments in a calendar view"""
    context = {
        'doctors': Doctor.objects.all(),
        'clinics': Clinic.objects.all(),
    }
    return render(request, 'scheduling/appointment_calendar.html', context)

@login_required
def get_calendar_appointments(request):
    """API endpoint to get appointments for the calendar"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    doctor_id = request.GET.get('doctor') 
    
    appointments = Appointment.objects.all()  # Use users.Appointment
    
    if start_date:
        # Parse the ISO date string and extract just the date part
        try:
            # Handle ISO format with timezone info
            from dateutil import parser
            parsed_date = parser.parse(start_date).date()
            appointments = appointments.filter(appointment_date__gte=parsed_date)
        except Exception as e:
            # Fallback if parsing fails
            print(f"Error parsing start date: {e}")
    
    if end_date:
        # Parse the ISO date string and extract just the date part
        try:
            # Handle ISO format with timezone info
            from dateutil import parser
            parsed_date = parser.parse(end_date).date()
            appointments = appointments.filter(appointment_date__lte=parsed_date)
        except Exception as e:
            # Fallback if parsing fails
            print(f"Error parsing end date: {e}")
    
    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)
        
    # If user is a doctor, show only their appointments
    if hasattr(request.user, 'doctor'):
        appointments = appointments.filter(doctor=request.user.doctor)
    
    events = []
    for appointment in appointments:
        # Different colors for different statuses
        color_map = {
            'scheduled': '#3788d8',
            'completed': '#28a745',
            'cancelled': '#dc3545',
            'no_show': '#fd7e14',
            'missed': '#17a2b8',
        }
        
        # Create the appointment datetime
        start_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )
        
        # Assume appointments last 30 minutes
        end_datetime = start_datetime + timedelta(minutes=30)
        
        # Get scheduling info if available
        scheduling_info = None
        try:
            scheduling_info = ScheduledAppointment.objects.get(appointment=appointment)
        except ScheduledAppointment.DoesNotExist:
            pass
        
        events.append({
            'id': appointment.id,
            'title': f"{appointment.patient} - {appointment.doctor}",
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'color': color_map.get(appointment.status, '#3788d8'),
            'extendedProps': {
                'patient': str(appointment.patient),
                'doctor': str(appointment.doctor),
                'status': appointment.get_status_display(),
                'reason': appointment.reason,
                'is_telemedicine': scheduling_info.is_telemedicine if scheduling_info else False,
                'is_emergency': scheduling_info.is_emergency if scheduling_info else False,
            },
            'url': reverse_lazy('scheduling:appointment_detail', args=[appointment.id]),
        })
    
    return JsonResponse(events, safe=False)

@login_required
def get_available_slots(request):
    """Get available appointment slots for a doctor on a given date"""
    doctor_id = request.GET.get('doctor')
    date_str = request.GET.get('date')
    
    if not doctor_id or not date_str:
        return JsonResponse({'error': 'Doctor and date are required'}, status=400)
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        print(f"Finding slots for Doctor: {doctor}, Date: {date}")
    except (Doctor.DoesNotExist, ValueError):
        print(f"Invalid doctor ID: {doctor_id} or date format: {date_str}")
        return JsonResponse({'error': 'Invalid doctor or date format'}, status=400)
    
    # Get day of week (0 = Monday, 6 = Sunday)
    day_of_week = date.weekday()
    print(f"Day of week: {day_of_week}")
    
    # Check if it's a holiday
    holiday_exists = Holiday.objects.filter(
        date=date,
        doctor=doctor
    ).exists() or Holiday.objects.filter(
        date=date,
        clinic=doctor.clinic,
        is_clinic_holiday=True
    ).exists()
    
    if holiday_exists:
        print(f"Date {date} is a holiday for doctor {doctor}")
        return JsonResponse({'slots': [], 'message': 'This is a holiday.'})
    
    # Get doctor's schedule for this day
    schedules = AppointmentSchedule.objects.filter(
        doctor=doctor,
        day_of_week=day_of_week,
        is_active=True
    )
    
    print(f"Found {schedules.count()} schedules for doctor on this day")
    
    if not schedules.exists():
        print(f"No schedule found for doctor {doctor} on day {day_of_week}")
        return JsonResponse({'slots': [], 'message': 'No schedule available for this day.'})
    
    # Get all existing appointments for this doctor and date
    existing_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=date,
        status__in=['scheduled', 'completed']
    ).values_list('appointment_time', flat=True)
    
    # Convert to set for faster lookups
    booked_times = set(existing_appointments)
    print(f"Found {len(booked_times)} existing appointments")
    
    available_slots = []
    
    for schedule in schedules:
        print(f"Processing schedule: {schedule.start_time} - {schedule.end_time}, duration: {schedule.appointment_duration} minutes")
        slot_start = schedule.start_time
        slot_end = datetime.combine(date, schedule.end_time)
        
        # Duration in minutes
        duration = schedule.appointment_duration
        
        # Generate slots
        current_slot = datetime.combine(date, slot_start)
        
        slot_count = 0
        while current_slot.time() < schedule.end_time:
            # Check if slot is during break time
            is_break_time = False
            if schedule.break_start_time and schedule.break_end_time:
                if schedule.break_start_time <= current_slot.time() < schedule.break_end_time:
                    is_break_time = True
                    print(f"Slot {current_slot.time()} is during break time")
            
            # If not during break and not already booked
            if not is_break_time and current_slot.time() not in booked_times:
                available_slots.append({
                    'time': current_slot.strftime('%H:%M'),
                    'formatted_time': current_slot.strftime('%I:%M %p')
                })
                slot_count += 1
            elif is_break_time:
                print(f"Skipping slot {current_slot.time()} - during break")
            elif current_slot.time() in booked_times:
                print(f"Skipping slot {current_slot.time()} - already booked")
            
            # Move to next slot
            current_slot = current_slot + timedelta(minutes=duration)
        
        print(f"Generated {slot_count} available slots for this schedule")
    
    print(f"Total available slots: {len(available_slots)}")
    return JsonResponse({'slots': available_slots})

@require_POST
@login_required
def change_appointment_status(request, pk):
    """Change the status of an appointment"""
    appointment = get_object_or_404(Appointment, pk=pk)  # Use users.Appointment
    status = request.POST.get('status')
    
    if status and status in dict(Appointment.STATUS_CHOICES):
        appointment.status = status
        appointment.save()
        messages.success(request, f'Appointment status changed to {appointment.get_status_display()}.')
    else:
        messages.error(request, 'Invalid status.')
    
    return redirect('scheduling:appointment_detail', pk=pk)

@login_required
def dashboard(request):
    """Dashboard view for scheduling app"""
    today = timezone.now().date()
    
    # Get today's appointments using users.Appointment
    today_appointments_query = Appointment.objects.filter(
        appointment_date=today
    ).order_by('appointment_time')
    
    # Get upcoming appointments (next 7 days, excluding today)
    upcoming_date = today + timedelta(days=7)
    upcoming_appointments_query = Appointment.objects.filter(
        appointment_date__gt=today,
        appointment_date__lte=upcoming_date
    ).order_by('appointment_date', 'appointment_time')
    
    # If user is a doctor, filter appointments by doctor
    if hasattr(request.user, 'doctor'):
        today_appointments_query = today_appointments_query.filter(doctor=request.user.doctor)
        upcoming_appointments_query = upcoming_appointments_query.filter(doctor=request.user.doctor)
    
    # Now apply the slicing after all filters
    today_appointments = today_appointments_query
    upcoming_appointments = upcoming_appointments_query[:5]  # Limit to 5
    
    # Get appointment counts for stats
    today_count = today_appointments.count()
    upcoming_count = Appointment.objects.filter(
        appointment_date__gt=today
    ).count()
    
    # Week range for confirmed count
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    confirmed_count = Appointment.objects.filter(
        status='completed',  # Use 'completed' instead of 'confirmed'
        appointment_date__range=[week_start, week_end]
    ).count()
    
    pending_count = Appointment.objects.filter(
        status='scheduled'
    ).count()
    
    # Last 30 days for no-shows
    thirty_days_ago = today - timedelta(days=30)
    no_show_count = Appointment.objects.filter(
        status='no_show',
        appointment_date__gte=thirty_days_ago,
        appointment_date__lte=today
    ).count()
    
    # Get all doctors for admin/staff view
    doctors = []
    appointment_types = []
    upcoming_holidays = []
    
    if request.user.is_staff or request.user.is_superuser:
        doctors = Doctor.objects.all()
        
        # Get doctor's schedule for today
        day_of_week = today.weekday()  # 0 is Monday, 6 is Sunday
        for doctor in doctors:
            try:
                doctor.todaySchedule = AppointmentSchedule.objects.filter(
                    doctor=doctor,
                    day_of_week=day_of_week,
                    is_active=True
                ).first()
            except:
                doctor.todaySchedule = None
        
        # Get appointment types from our scheduling system
        appointment_types_query = AppointmentType.objects.filter(is_active=True)
        appointment_types = appointment_types_query[:5]
        
        # Get upcoming holidays
        upcoming_holidays = Holiday.objects.filter(
            date__gte=today
        ).order_by('date')[:5]
    
    context = {
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'today_count': today_count,
        'upcoming_count': upcoming_count,
        'confirmed_count': confirmed_count,
        'pending_count': pending_count,
        'no_show_count': no_show_count,
        'doctors': doctors,
        'appointment_types': appointment_types,
        'upcoming_holidays': upcoming_holidays
    }
    
    return render(request, 'scheduling/dashboard.html', context)

# Admin Views for Schedules
class ScheduleListView(LoginRequiredMixin, ListView):
    model = AppointmentSchedule
    template_name = 'scheduling/admin/schedule_list.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        return AppointmentSchedule.objects.all().order_by('doctor', 'day_of_week')

class ScheduleDetailView(LoginRequiredMixin, DetailView):
    model = AppointmentSchedule
    template_name = 'scheduling/admin/schedule_detail.html'
    context_object_name = 'schedule'

class ScheduleCreateView(LoginRequiredMixin, CreateView):
    model = AppointmentSchedule
    form_class = AppointmentScheduleForm
    template_name = 'scheduling/admin/schedule_form.html'
    success_url = reverse_lazy('scheduling:schedule_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Schedule created successfully.')
        return super().form_valid(form)

class ScheduleUpdateView(LoginRequiredMixin, UpdateView):
    model = AppointmentSchedule
    form_class = AppointmentScheduleForm
    template_name = 'scheduling/admin/schedule_form.html'
    success_url = reverse_lazy('scheduling:schedule_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Schedule updated successfully.')
        return super().form_valid(form)

class ScheduleDeleteView(LoginRequiredMixin, DeleteView):
    model = AppointmentSchedule
    template_name = 'scheduling/admin/schedule_confirm_delete.html'
    success_url = reverse_lazy('scheduling:schedule_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Schedule deleted successfully.')
        return super().delete(request, *args, **kwargs)

# Admin Views for Doctors
class DoctorListView(LoginRequiredMixin, ListView):
    model = Doctor
    template_name = 'scheduling/admin/doctor_list.html'
    context_object_name = 'doctors'

class DoctorDetailView(LoginRequiredMixin, DetailView):
    model = Doctor
    template_name = 'scheduling/admin/doctor_detail.html'
    context_object_name = 'doctor'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedules'] = AppointmentSchedule.objects.filter(doctor=self.object)
        context['appointments'] = ScheduledAppointment.objects.filter(appointment__doctor=self.object)
        return context

class DoctorUpdateView(LoginRequiredMixin, UpdateView):
    model = Doctor
    fields = ['is_active', 'clinic', 'specialization']
    template_name = 'scheduling/admin/doctor_form.html'
    success_url = reverse_lazy('scheduling:doctor_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Doctor information updated successfully.')
        return super().form_valid(form)

# Admin Views for Holidays
class HolidayListView(LoginRequiredMixin, ListView):
    model = Holiday
    template_name = 'scheduling/admin/holiday_list.html'
    context_object_name = 'holidays'
    
    def get_queryset(self):
        return Holiday.objects.all().order_by('date')

class HolidayDetailView(LoginRequiredMixin, DetailView):
    model = Holiday
    template_name = 'scheduling/admin/holiday_detail.html'
    context_object_name = 'holiday'

class HolidayCreateView(LoginRequiredMixin, CreateView):
    model = Holiday
    form_class = HolidayForm
    template_name = 'scheduling/admin/holiday_form.html'
    success_url = reverse_lazy('scheduling:holiday_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Holiday created successfully.')
        return super().form_valid(form)

class HolidayUpdateView(LoginRequiredMixin, UpdateView):
    model = Holiday
    form_class = HolidayForm
    template_name = 'scheduling/admin/holiday_form.html'
    success_url = reverse_lazy('scheduling:holiday_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Holiday updated successfully.')
        return super().form_valid(form)

class HolidayDeleteView(LoginRequiredMixin, DeleteView):
    model = Holiday
    template_name = 'scheduling/admin/holiday_confirm_delete.html'
    success_url = reverse_lazy('scheduling:holiday_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Holiday deleted successfully.')
        return super().delete(request, *args, **kwargs)

# Admin Views for Appointment Types - Using django-appointment
class AppointmentTypeListView(LoginRequiredMixin, ListView):
    template_name = 'scheduling/admin/appointment_type_list.html'
    context_object_name = 'appointment_types'
    
    def get_queryset(self):
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                return AppointmentType.objects.all()
            except LookupError:
                # The model doesn't exist in the installed app
                messages.warning(self.request, "The AppointmentType model doesn't exist in the appointment app.")
        else:
            messages.warning(self.request, "The django-appointment app is not installed.")
        return []

class AppointmentTypeCreateView(LoginRequiredMixin, CreateView):
    template_name = 'scheduling/admin/appointment_type_form.html'
    success_url = reverse_lazy('scheduling:appointment_type_list')
    
    def get_form_class(self):
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                from django import forms
                
                class AppointmentTypeForm(forms.ModelForm):
                    class Meta:
                        model = AppointmentType
                        fields = ['name', 'duration', 'color', 'description']
                        widgets = {
                            'color': forms.TextInput(attrs={'type': 'color'}),
                        }
                
                return AppointmentTypeForm
            except LookupError:
                messages.error(self.request, "The AppointmentType model doesn't exist in the appointment app.")
                return None
        messages.error(self.request, "The django-appointment app is not installed.")
        return None
    
    def get(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        if form_class is None:
            return redirect('scheduling:appointment_type_list')
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment type created successfully.')
        return super().form_valid(form)

class AppointmentTypeUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'scheduling/admin/appointment_type_form.html'
    success_url = reverse_lazy('scheduling:appointment_type_list')
    
    def get_queryset(self):
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                return AppointmentType.objects.all()
            except LookupError:
                messages.error(self.request, "The AppointmentType model doesn't exist in the appointment app.")
                return None
        messages.error(self.request, "The django-appointment app is not installed.")
        return None
    
    def get_form_class(self):
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                from django import forms
                
                class AppointmentTypeForm(forms.ModelForm):
                    class Meta:
                        model = AppointmentType
                        fields = ['name', 'duration', 'color', 'description']
                        widgets = {
                            'color': forms.TextInput(attrs={'type': 'color'}),
                        }
                
                return AppointmentTypeForm
            except LookupError:
                return None
        return None
    
    def get(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        if form_class is None:
            return redirect('scheduling:appointment_type_list')
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment type updated successfully.')
        return super().form_valid(form)

class AppointmentTypeDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'scheduling/admin/appointment_type_confirm_delete.html'
    success_url = reverse_lazy('scheduling:appointment_type_list')
    
    def get_queryset(self):
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                return AppointmentType.objects.all()
            except LookupError:
                messages.error(self.request, "The AppointmentType model doesn't exist in the appointment app.")
                return None
        messages.error(self.request, "The django-appointment app is not installed.")
        return None
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if queryset is None:
            return redirect('scheduling:appointment_type_list')
        return super().get(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Appointment type deleted successfully.')
        return super().delete(request, *args, **kwargs)

# Scheduling Settings Page
@login_required
def scheduling_settings(request):
    """Admin settings for scheduling system"""
    from django.apps import apps
    
    # Check if django-appointment is installed
    has_appointment_app = apps.is_installed('appointment')
    
    # Get or create settings instance
    settings = SchedulingSettings.get_settings()
    
    if request.method == 'POST':
        setting_category = request.POST.get('setting_category')
        
        if setting_category == 'general':
            # Update general settings
            settings.default_appointment_duration = int(request.POST.get('default_appointment_duration', 30))
            settings.min_scheduling_notice = int(request.POST.get('min_scheduling_notice', 24))
            settings.max_days_in_advance = int(request.POST.get('max_days_in_advance', 90))
            settings.buffer_between_appointments = int(request.POST.get('buffer_between_appointments', 5))
            settings.default_start_time = request.POST.get('default_start_time', '09:00')
            settings.default_end_time = request.POST.get('default_end_time', '17:00')
            settings.save()
            messages.success(request, 'General settings updated successfully.')
            
        elif setting_category == 'notifications':
            # Update notification settings
            settings.send_confirmation_emails = 'send_confirmation_emails' in request.POST
            settings.send_reminder_emails = 'send_reminder_emails' in request.POST
            settings.reminder_hours = int(request.POST.get('reminder_hours', 24))
            settings.send_sms_reminders = 'send_sms_reminders' in request.POST
            settings.sms_reminder_hours = int(request.POST.get('sms_reminder_hours', 2))
            settings.save()
            messages.success(request, 'Notification settings updated successfully.')
        
        return redirect('scheduling:settings')
    
    context = {
        'has_appointment_app': has_appointment_app,
        'settings': settings,
    }
    
    return render(request, 'scheduling/admin/settings.html', context)

@login_required
def integrated_appointment_create(request):
    """Create appointment using the existing appointment system but with scheduling integration"""
    try:
        if hasattr(request.user, 'doctor'):
            doctor = request.user.doctor
            
            if request.method == 'POST':
                form = AppointmentForm(request.POST, user=request.user)
                if form.is_valid():
                    # Create appointment using the existing Appointment model from users app
                    from users.models import Appointment as UserAppointment
                    
                    appointment = UserAppointment.objects.create(
                        doctor=doctor,
                        patient=form.cleaned_data['patient'],
                        appointment_date=form.cleaned_data['appointment_date'],
                        appointment_time=form.cleaned_data['appointment_time'],
                        reason=form.cleaned_data['reason'],
                        status='scheduled'
                    )
                    
                    # Mark the slot as booked if it exists
                    from users.models import AppointmentSlot
                    slot = AppointmentSlot.objects.filter(
                        doctor=doctor,
                        date=form.cleaned_data['appointment_date'],
                        start_time=form.cleaned_data['appointment_time'],
                        is_booked=False
                    ).first()
                    
                    if slot:
                        slot.is_booked = True
                        slot.save()
                    
                    messages.success(request, 'Appointment scheduled successfully!')
                    return redirect('scheduling:dashboard')
            else:
                form = AppointmentForm(user=request.user)
                
            context = {
                'form': form,
                'doctor': doctor,
                'min_date': timezone.now().date().isoformat(),
            }
            return render(request, 'scheduling/appointment_form.html', context)
        else:
            messages.error(request, 'Only doctors can create appointments')
            return redirect('scheduling:dashboard')
            
    except Exception as e:
        messages.error(request, f'Error creating appointment: {str(e)}')
        return redirect('scheduling:dashboard')

@login_required
def sync_with_existing_appointments(request):
    """Sync scheduling system with existing appointments"""
    try:
        # Import existing appointment model
        from users.models import Appointment as UserAppointment
        
        # Get all existing appointments that don't have scheduling counterparts
        user_appointments = UserAppointment.objects.all()
        synced_count = 0
        
        for user_appointment in user_appointments:
            # Check if this appointment already has a bridge record
            existing_scheduled = ScheduledAppointment.objects.filter(
                appointment=user_appointment
            ).exists()
            
            if not existing_scheduled:
                # Create corresponding scheduled appointment bridge
                ScheduledAppointment.objects.create(
                    appointment=user_appointment,
                    is_telemedicine=False,
                    is_emergency=False,
                    is_walk_in=getattr(user_appointment, 'is_walk_in', False),
                    notes='',
                    created_by=user_appointment.doctor.user
                )
                synced_count += 1
        
        messages.success(request, f'Successfully synced {synced_count} appointments with scheduling system')
        return redirect('scheduling:dashboard')
        
    except Exception as e:
        messages.error(request, f'Error syncing appointments: {str(e)}')
        return redirect('scheduling:dashboard')

@login_required 
def generate_slots_from_existing_availability(request):
    """Generate slots using existing DoctorAvailability from users app"""
    try:
        if not hasattr(request.user, 'doctor'):
            messages.error(request, 'Only doctors can generate slots')
            return redirect('scheduling:dashboard')
            
        doctor = request.user.doctor
        
        # Import existing availability model
        from users.models import DoctorAvailability, AppointmentSlot
        
        # Get existing availability
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            is_available=True
        )
        
        if not availabilities.exists():
            messages.warning(request, 'No availability found. Please set up your availability first.')
            return redirect('users:manage_availability')
        
        # Also create scheduling system availability if it doesn't exist
        for availability in availabilities:
            schedule, created = AppointmentSchedule.objects.get_or_create(
                doctor=doctor,
                clinic=doctor.clinic,
                day_of_week=availability.day_of_week,
                defaults={
                    'start_time': availability.start_time,
                    'end_time': availability.end_time,
                    'appointment_duration': 30,  # Default 30 minutes
                    'is_active': availability.is_available
                }
            )
            
            if created:
                print(f"Created scheduling availability for {doctor} on day {availability.day_of_week}")
        
        # Generate slots for next 30 days
        today = timezone.now().date()
        end_date = today + timedelta(days=30)
        slots_created = 0
        
        current_date = today
        while current_date <= end_date:
            # Get availability for current day
            day_availability = availabilities.filter(
                day_of_week=current_date.weekday()
            ).first()
            
            if day_availability:
                # Delete existing unbooked slots for this date
                AppointmentSlot.objects.filter(
                    doctor=doctor,
                    date=current_date,
                    is_booked=False
                ).delete()
                
                # Generate new slots
                try:
                    slots = day_availability.generate_slots(current_date)
                    for slot_time in slots:
                        slot, created = AppointmentSlot.objects.get_or_create(
                            doctor=doctor,
                            date=current_date,
                            start_time=slot_time.time(),
                            end_time=(slot_time + timedelta(minutes=30)).time(),
                            defaults={'is_booked': False}
                        )
                        if created:
                            slots_created += 1
                except Exception as e:
                    print(f"Error generating slots for {current_date}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        messages.success(request, f'Generated {slots_created} appointment slots')
        return redirect('scheduling:dashboard')
        
    except Exception as e:
        messages.error(request, f'Error generating slots: {str(e)}')
        return redirect('scheduling:dashboard')
