from django.contrib import admin
from .models import (
    Bill, BillItem, Payment, BillingItem, 
    LabTestBilling, ConsultationBilling, InsuranceClaim
)


class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 1
    readonly_fields = ['total']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    readonly_fields = ['receipt_number']


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'patient', 'bill_date', 'total', 'status', 'is_paid']
    list_filter = ['status', 'is_paid', 'bill_date', 'bill_type']
    search_fields = ['bill_number', 'patient__first_name', 'patient__last_name', 'notes']
    readonly_fields = ['bill_number', 'subtotal', 'total']
    date_hierarchy = 'bill_date'
    inlines = [BillItemInline, PaymentInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('bill_number', 'bill_date', 'due_date', 'bill_type', 'reference_id')
        }),
        ('Relationships', {
            'fields': ('patient', 'doctor', 'clinic', 'appointment', 'lab_test')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax', 'discount', 'total', 'status', 'is_paid', 'payment_method')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'bill', 'amount', 'payment_date', 'payment_method']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['receipt_number', 'transaction_id', 'bill__bill_number']
    readonly_fields = ['receipt_number']
    date_hierarchy = 'payment_date'


@admin.register(BillingItem)
class BillingItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'item_code', 'item_type', 'price', 'clinic', 'is_active']
    list_filter = ['item_type', 'is_active', 'clinic']
    search_fields = ['name', 'item_code', 'description']


@admin.register(LabTestBilling)
class LabTestBillingAdmin(admin.ModelAdmin):
    list_display = ['lab_test', 'bill', 'base_price', 'final_price', 'is_home_collection']
    list_filter = ['is_home_collection']
    search_fields = ['lab_test__test_definition__name', 'bill__bill_number']


@admin.register(ConsultationBilling)
class ConsultationBillingAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'bill', 'base_fee', 'final_fee', 'is_followup']
    list_filter = ['is_followup']
    search_fields = ['appointment__patient__first_name', 'appointment__patient__last_name', 'bill__bill_number']


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ['claim_number', 'bill', 'patient', 'insurance_provider', 'claimed_amount', 'status']
    list_filter = ['status', 'claim_date', 'insurance_provider']
    search_fields = ['claim_number', 'policy_number', 'patient__first_name', 'patient__last_name', 'bill__bill_number']
    readonly_fields = ['claim_number']
    date_hierarchy = 'claim_date' 