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
from .models import AppointmentSchedule, Holiday, ScheduledAppointment
from users.models import Doctor, Patient, Clinic
from .forms import AppointmentForm, AppointmentScheduleForm, HolidayForm

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
    model = ScheduledAppointment
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
            
        clinic_id = self.request.GET.get('clinic')
        if clinic_id:
            queryset = queryset.filter(clinic_id=clinic_id)
            
        # If user is a doctor, show only their appointments
        if hasattr(self.request.user, 'doctor'):
            queryset = queryset.filter(doctor=self.request.user.doctor)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doctors'] = Doctor.objects.all()
        context['clinics'] = Clinic.objects.all()
        context['statuses'] = dict(ScheduledAppointment._meta.get_field('status').choices)
        
        # Add filters to context
        context['filters'] = {
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
            'status': self.request.GET.get('status', ''),
            'doctor': self.request.GET.get('doctor', ''),
            'clinic': self.request.GET.get('clinic', ''),
        }
        return context

class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model = ScheduledAppointment
    template_name = 'scheduling/appointment_detail.html'
    context_object_name = 'appointment'

class AppointmentCreateView(LoginRequiredMixin, CreateView):
    model = ScheduledAppointment
    form_class = AppointmentForm
    template_name = 'scheduling/appointment_form.html'
    success_url = reverse_lazy('scheduling:appointment_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Appointment created successfully.')
        return super().form_valid(form)

class AppointmentUpdateView(LoginRequiredMixin, UpdateView):
    model = ScheduledAppointment
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
    model = ScheduledAppointment
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
    clinic_id = request.GET.get('clinic')
    
    appointments = ScheduledAppointment.objects.all()
    
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
    if clinic_id:
        appointments = appointments.filter(clinic_id=clinic_id)
        
    # If user is a doctor, show only their appointments
    if hasattr(request.user, 'doctor'):
        appointments = appointments.filter(doctor=request.user.doctor)
    
    events = []
    for appointment in appointments:
        # Different colors for different statuses
        color_map = {
            'scheduled': '#3788d8',
            'confirmed': '#28a745',
            'completed': '#6c757d',
            'cancelled': '#dc3545',
            'no_show': '#fd7e14',
            'rescheduled': '#17a2b8',
        }
        
        # Create the appointment datetime
        start_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )
        
        # Assume appointments last 30 minutes
        end_datetime = start_datetime + timedelta(minutes=30)
        
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
    existing_appointments = ScheduledAppointment.objects.filter(
        doctor=doctor,
        appointment_date=date,
        status__in=['scheduled', 'confirmed']
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
    appointment = get_object_or_404(ScheduledAppointment, pk=pk)
    status = request.POST.get('status')
    
    if status and status in dict(ScheduledAppointment._meta.get_field('status').choices):
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
    # Get today's appointments
    today_appointments_query = ScheduledAppointment.objects.filter(
        appointment_date=today
    ).order_by('appointment_time')
    
    # Get upcoming appointments (next 7 days, excluding today)
    upcoming_date = today + timedelta(days=7)
    upcoming_appointments_query = ScheduledAppointment.objects.filter(
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
    upcoming_count = ScheduledAppointment.objects.filter(
        appointment_date__gt=today
    ).count()
    
    # Week range for confirmed count
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    confirmed_count = ScheduledAppointment.objects.filter(
        status='confirmed',
        appointment_date__range=[week_start, week_end]
    ).count()
    
    pending_count = ScheduledAppointment.objects.filter(
        status='scheduled'
    ).count()
    
    # Last 30 days for no-shows
    thirty_days_ago = today - timedelta(days=30)
    no_show_count = ScheduledAppointment.objects.filter(
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
        
        # Get appointment types
        from django.apps import apps
        if apps.is_installed('appointment'):
            try:
                AppointmentType = apps.get_model('appointment', 'AppointmentType')
                # Apply all filters first then slice
                appointment_types_query = AppointmentType.objects.all()
                appointment_types = appointment_types_query[:5]
            except LookupError:
                # The model doesn't exist in the installed app
                pass
        
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
        context['appointments'] = ScheduledAppointment.objects.filter(doctor=self.object)
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
        return Holiday.objects.all().order_by('-date')

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
    success_url = reverse_lazy('scheduling:appointment_types')
    
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
            return redirect('scheduling:appointment_types')
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment type created successfully.')
        return super().form_valid(form)

class AppointmentTypeUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'scheduling/admin/appointment_type_form.html'
    success_url = reverse_lazy('scheduling:appointment_types')
    
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
            return redirect('scheduling:appointment_types')
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Appointment type updated successfully.')
        return super().form_valid(form)

class AppointmentTypeDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'scheduling/admin/appointment_type_confirm_delete.html'
    success_url = reverse_lazy('scheduling:appointment_types')
    
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
            return redirect('scheduling:appointment_types')
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
    
    context = {
        'has_appointment_app': has_appointment_app,
    }
    
    if request.method == 'POST':
        # Process settings form
        setting_name = request.POST.get('setting_name')
        setting_value = request.POST.get('setting_value')
        
        # Save setting (implementation depends on your settings storage mechanism)
        messages.success(request, f'Setting "{setting_name}" updated successfully.')
        return redirect('scheduling:settings')
    
    return render(request, 'scheduling/admin/settings.html', context)
