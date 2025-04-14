from django.contrib import admin
from .models import LabProfile, TestDefinition, ExternalLabTestOffering

@admin.register(LabProfile)
class LabProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_approved', 'created_at')
    list_editable = ('is_approved',)
    list_filter = ('is_approved',)
    search_fields = ('name', 'email')
    ordering = ('name',)

@admin.register(TestDefinition)
class TestDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code')
    search_fields = ('name', 'short_code')
    ordering = ('name',)

@admin.register(ExternalLabTestOffering)
class ExternalLabTestOfferingAdmin(admin.ModelAdmin):
    list_display = ('lab_profile', 'test', 'price', 'turnaround_time_hours', 
                   'offers_home_collection', 'is_active')
    list_filter = ('lab_profile', 'test', 'is_active')
    search_fields = ('lab_profile__name', 'test__name')
    ordering = ('lab_profile', 'test')
