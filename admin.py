from django.contrib import admin
from django.utils.html import format_html
from .models import Clinic, Doctor, Staff, UserProfile, Patient, Appointment, Prescription

# First unregister if models are already registered
try:
    admin.site.unregister(Doctor)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(UserProfile)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Patient)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Appointment)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Prescription)
except admin.sites.NotRegistered:
    pass

# Now register with new admin classes
@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'email', 'phone_number')
    search_fields = ('name', 'registration_number', 'email')
    list_filter = ('name',)
    
    def display_logo(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="50" height="50" />', obj.logo.url)
        return "No logo"
    display_logo.short_description = 'Logo'

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'license_number', 'specialization', 'verified')
    search_fields = ('name', 'license_number')
    list_filter = ('verified', 'specialization')
    actions = ['verify_doctors']

    def verify_doctors(self, request, queryset):
        queryset.update(verified=True)
    verify_doctors.short_description = "Mark selected doctors as verified"

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'clinic', 'is_active')
    search_fields = ('user__username', 'user__email')
    list_filter = ('role', 'is_active')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'clinic')
    search_fields = ('user__username', 'user__email', 'phone_number')
    list_filter = ('clinic',)

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'first_name', 'last_name', 'phone_number', 'email')
    search_fields = ('patient_id', 'first_name', 'last_name', 'phone_number')
    list_filter = ('gender',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'status')
    list_filter = ('status', 'appointment_date')
    search_fields = ('patient__first_name', 'doctor__name')

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'date')
    list_filter = ('date',)
    search_fields = ('patient__first_name', 'doctor__name')
