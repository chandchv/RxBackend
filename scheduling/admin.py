from django.contrib import admin
from .models import AppointmentSchedule, Holiday, ScheduledAppointment

@admin.register(AppointmentSchedule)
class AppointmentScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'clinic', 'day_of_week', 'start_time', 'end_time', 'is_active')
    list_filter = ('clinic', 'doctor', 'day_of_week', 'is_active')
    search_fields = ('doctor__name', 'clinic__name')
    
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'clinic', 'doctor', 'is_clinic_holiday')
    list_filter = ('is_clinic_holiday', 'date', 'clinic')
    search_fields = ('name', 'description')
    date_hierarchy = 'date'

@admin.register(ScheduledAppointment)
class ScheduledAppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'clinic', 'appointment_date', 'appointment_time', 'status')
    list_filter = ('status', 'clinic', 'doctor', 'is_emergency', 'is_telemedicine', 'is_walk_in')
    search_fields = ('patient__first_name', 'patient__last_name', 'doctor__name', 'reason', 'notes')
    date_hierarchy = 'appointment_date'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('patient', 'doctor', 'clinic', 'appointment_date', 'appointment_time', 'status')
        }),
        ('Appointment Details', {
            'fields': ('reason', 'is_telemedicine', 'is_emergency', 'is_walk_in', 'token_number', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
