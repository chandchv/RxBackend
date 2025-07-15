from django.contrib import admin
from .models import (
    LabProfile, TestDefinition, LabTestOffering, ExternalLabTestOffering,
    LabOrder, LabOrderTest, LabResult, CommissionRule, CommissionLedger,
    # New models
    SpecimenContainer, Specimen, SpecimenProcessing,
    QualityControlTest, QCResult,
    LabReport, TestResult,
    ReportDelivery, CommunicationLog,
    B2BPartner, B2BInvoice, B2BInvoiceItem,
    LabAnalytics, LabUser
)

@admin.register(LabProfile)
class LabProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone_number', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['name', 'email', 'contact_person']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(TestDefinition)
class TestDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_code', 'category', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'short_code', 'description']

@admin.register(LabTestOffering)
class LabTestOfferingAdmin(admin.ModelAdmin):
    list_display = ['lab', 'test', 'price', 'turnaround_time_hours', 'is_active']
    list_filter = ['is_active', 'offers_home_collection']
    search_fields = ['lab__name', 'test__name']

@admin.register(ExternalLabTestOffering)
class ExternalLabTestOfferingAdmin(admin.ModelAdmin):
    list_display = ['lab_profile', 'test', 'price', 'turnaround_time_hours', 'is_active']
    list_filter = ['is_active', 'offers_home_collection']
    search_fields = ['lab_profile__name', 'test__name']

@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'status', 'payment_status', 'total_price', 'order_date']
    list_filter = ['status', 'payment_status', 'order_date']
    search_fields = ['patient__user__first_name', 'patient__user__last_name', 'doctor__name']
    readonly_fields = ['order_date', 'last_updated']

@admin.register(LabOrderTest)
class LabOrderTestAdmin(admin.ModelAdmin):
    list_display = ['order', 'test', 'price', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['order__id', 'test__name']

@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ['order', 'uploaded_at', 'uploaded_by_lab']
    list_filter = ['uploaded_at']
    search_fields = ['order__id']

@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ['lab', 'doctor_percentage', 'platform_percentage', 'is_active']
    list_filter = ['is_active']

@admin.register(CommissionLedger)
class CommissionLedgerAdmin(admin.ModelAdmin):
    list_display = ['order', 'user', 'amount', 'transaction_type', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['order__id', 'user__username']

# ===== SPECIMEN MANAGEMENT ADMIN =====

@admin.register(SpecimenContainer)
class SpecimenContainerAdmin(admin.ModelAdmin):
    list_display = ['barcode', 'container_type', 'lab_profile', 'is_available', 'created_at']
    list_filter = ['container_type', 'is_available', 'created_at']
    search_fields = ['barcode', 'lab_profile__name']
    readonly_fields = ['created_at']

@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    list_display = ['specimen_id', 'lab_order', 'specimen_type', 'collection_method', 'processing_priority', 'created_at']
    list_filter = ['specimen_type', 'collection_method', 'processing_priority', 'created_at']
    search_fields = ['specimen_id', 'lab_order__id', 'lab_order__patient__user__first_name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SpecimenProcessing)
class SpecimenProcessingAdmin(admin.ModelAdmin):
    list_display = ['specimen', 'received_at_lab', 'processing_started', 'processing_completed', 'quality_check_passed']
    list_filter = ['quality_check_passed', 'received_at_lab', 'processing_started']
    search_fields = ['specimen__specimen_id']

# ===== QUALITY CONTROL ADMIN =====

@admin.register(QualityControlTest)
class QualityControlTestAdmin(admin.ModelAdmin):
    list_display = ['name', 'test_definition', 'qc_type', 'frequency', 'is_active']
    list_filter = ['qc_type', 'frequency', 'is_active']
    search_fields = ['name', 'test_definition__name']

@admin.register(QCResult)
class QCResultAdmin(admin.ModelAdmin):
    list_display = ['qc_test', 'specimen', 'result_value', 'run_date', 'is_in_control', 'run_by']
    list_filter = ['is_in_control', 'run_date', 'qc_test__qc_type']
    search_fields = ['qc_test__name', 'specimen__specimen_id']
    readonly_fields = ['run_date']

# ===== REPORT MANAGEMENT ADMIN =====

@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = ['report_number', 'lab_order', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at', 'approved_at', 'released_at']
    search_fields = ['report_number', 'lab_order__id']
    readonly_fields = ['created_at']

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ['report', 'test_definition', 'result_value', 'unit', 'is_abnormal', 'performed_at']
    list_filter = ['is_abnormal', 'abnormality_type', 'performed_at']
    search_fields = ['report__report_number', 'test_definition__name']
    readonly_fields = ['performed_at', 'verified_at']

# ===== COMMUNICATION & DELIVERY ADMIN =====

@admin.register(ReportDelivery)
class ReportDeliveryAdmin(admin.ModelAdmin):
    list_display = ['report', 'recipient_type', 'delivery_method', 'status', 'sent_at']
    list_filter = ['recipient_type', 'delivery_method', 'status', 'sent_at']
    search_fields = ['report__report_number']
    readonly_fields = ['sent_at', 'delivered_at', 'read_at']

@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ['lab_profile', 'communication_type', 'recipient', 'delivery_method', 'status', 'sent_at']
    list_filter = ['communication_type', 'delivery_method', 'status', 'sent_at']
    search_fields = ['lab_profile__name', 'recipient__username', 'subject']
    readonly_fields = ['sent_at', 'delivered_at']

# ===== B2B AUTOMATION ADMIN =====

@admin.register(B2BPartner)
class B2BPartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'partner_type', 'contact_person', 'email', 'credit_days', 'is_active']
    list_filter = ['partner_type', 'is_active', 'created_at']
    search_fields = ['name', 'contact_person', 'email']
    readonly_fields = ['created_at']

@admin.register(B2BInvoice)
class B2BInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'partner', 'lab_profile', 'total_amount', 'status', 'invoice_date', 'due_date']
    list_filter = ['status', 'invoice_date', 'due_date']
    search_fields = ['invoice_number', 'partner__name', 'lab_profile__name']
    readonly_fields = ['created_at']

@admin.register(B2BInvoiceItem)
class B2BInvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'lab_order', 'test_name', 'quantity', 'unit_price', 'total_price']
    list_filter = ['invoice__status']
    search_fields = ['invoice__invoice_number', 'test_name']

# ===== ANALYTICS ADMIN =====

@admin.register(LabAnalytics)
class LabAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['lab_profile', 'date', 'total_orders', 'completed_orders', 'total_revenue']
    list_filter = ['date', 'lab_profile']
    search_fields = ['lab_profile__name']
    readonly_fields = ['date']

@admin.register(LabUser)
class LabUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'lab_profile', 'user_type', 'is_active', 'created_at']
    list_filter = ['user_type', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'lab_profile__name']
    readonly_fields = ['created_at', 'updated_at']
