from django.contrib import admin
from .models import AppointmentSchedule, Holiday, ScheduledAppointment, AppointmentType

@admin.register(AppointmentSchedule)
class AppointmentScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'clinic', 'day_of_week', 'start_time', 'end_time', 'is_active')
    list_filter = ('clinic', 'doctor', 'day_of_week', 'is_active')
    search_fields = ('doctor__user__first_name', 'doctor__user__last_name', 'clinic__name')
    list_per_page = 25

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'clinic', 'doctor', 'is_clinic_holiday')
    list_filter = ('is_clinic_holiday', 'date', 'clinic', 'doctor')
    search_fields = ('name', 'clinic__name', 'doctor__user__first_name', 'doctor__user__last_name')
    date_hierarchy = 'date'
    list_per_page = 25

@admin.register(ScheduledAppointment)
class ScheduledAppointmentAdmin(admin.ModelAdmin):
    list_display = ('get_appointment_info', 'get_patient', 'get_doctor', 'get_date', 'get_time', 'get_status', 'appointment_type', 'is_telemedicine', 'is_emergency')
    list_filter = ('appointment__status', 'appointment_type', 'is_telemedicine', 'is_emergency', 'is_walk_in', 'appointment__appointment_date')
    search_fields = (
        'appointment__patient__user__first_name', 
        'appointment__patient__user__last_name',
        'appointment__doctor__user__first_name', 
        'appointment__doctor__user__last_name',
        'appointment__reason'
    )
    date_hierarchy = 'appointment__appointment_date'
    list_per_page = 25
    raw_id_fields = ('appointment', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Appointment Reference', {
            'fields': ('appointment',)
        }),
        ('Scheduling Details', {
            'fields': ('appointment_type', 'is_telemedicine', 'is_emergency', 'is_walk_in')
        }),
        ('Additional Information', {
            'fields': ('notes', 'django_appointment_id')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_appointment_info(self, obj):
        return str(obj.appointment)
    get_appointment_info.short_description = 'Appointment'
    get_appointment_info.admin_order_field = 'appointment'
    
    def get_patient(self, obj):
        return obj.patient
    get_patient.short_description = 'Patient'
    get_patient.admin_order_field = 'appointment__patient'
    
    def get_doctor(self, obj):
        return obj.doctor
    get_doctor.short_description = 'Doctor'
    get_doctor.admin_order_field = 'appointment__doctor'
    
    def get_date(self, obj):
        return obj.appointment_date
    get_date.short_description = 'Date'
    get_date.admin_order_field = 'appointment__appointment_date'
    
    def get_time(self, obj):
        return obj.appointment_time
    get_time.short_description = 'Time'
    get_time.admin_order_field = 'appointment__appointment_time'
    
    def get_status(self, obj):
        return obj.status
    get_status.short_description = 'Status'
    get_status.admin_order_field = 'appointment__status'

@admin.register(AppointmentType)
class AppointmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration', 'color', 'is_active', 'created_at')
    list_filter = ('is_active', 'duration')
    search_fields = ('name', 'description')
    ordering = ('name',)
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'duration', 'color', 'is_active')
        }),
        ('Description', {
            'fields': ('description',)
        }),
    )
