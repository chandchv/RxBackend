from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import Clinic, Doctor, UserProfile, Patient, Appointment, Prescription, PrescriptionItem, ClinicAdmin

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

@admin.register(ClinicAdmin)
class ClinicAdminAdmin(admin.ModelAdmin):
    list_display = ('user', 'clinic', 'created_at')
    search_fields = ('user__username', 'clinic__name')
    list_filter = ('created_at',)

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
    list_display = ('name', 'license_number', 'specialization', 'clinic', 'verified', 'is_active')
    list_filter = ('verified', 'is_active', 'clinic', 'specialization')
    search_fields = ('name', 'license_number', 'email', 'phone_number')
    readonly_fields = ('id',)  # Make ID field read-only
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'clinic', 'name', 'specialization', 'license_number', 'medical_council')
        }),
        ('Contact Details', {
            'fields': ('email', 'phone_number', 'address', 'pincode')
        }),
        ('Professional Details', {
            'fields': ('consultation_fee', 'date_of_registration', 'qualification', 'experience')
        }),
        ('Status', {
            'fields': ('is_active', 'verified', 'verification_details')
        }),
    )
    actions = ['verify_doctors', 'activate_doctors', 'deactivate_doctors']

    def verify_doctors(self, request, queryset):
        queryset.update(verified=True)
    verify_doctors.short_description = "Mark selected doctors as verified"

    def activate_doctors(self, request, queryset):
        queryset.update(is_active=True)
    activate_doctors.short_description = "Activate selected doctors"

    def deactivate_doctors(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_doctors.short_description = "Deactivate selected doctors"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'clinic')
    search_fields = ('user__username', 'user__email', 'phone_number')
    list_filter = ('clinic',)

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'email', 'phone_number', 'clinic', 'doctor']
    list_filter = ['clinic', 'doctor']
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Name'

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'status')
    list_filter = ('status', 'appointment_date')
    search_fields = ('patient__first_name', 'doctor__name')

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1  # Number of empty forms to display

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    inlines = [PrescriptionItemInline]
    list_display = ('patient', 'doctor', 'date', 'created_at')
    search_fields = ('patient__first_name', 'patient__last_name', 'doctor__name')
    list_filter = ('date', 'doctor')

@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ('medicine', 'dosage', 'duration', 'duration_unit')
    search_fields = ('medicine', 'prescription__patient__first_name')
    list_filter = ('prescription__date',)
