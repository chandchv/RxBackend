from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views, views

router = DefaultRouter()
router.register(r'bills', api_views.BillViewSet)

app_name = 'billing'
# DRF Router for API endpoints
router.register(r'billing-items', api_views.BillingItemViewSet)
router.register(r'lab-test-billing', api_views.LabTestBillingViewSet)
router.register(r'consultation-billing', api_views.ConsultationBillingViewSet)
router.register(r'insurance-claims', api_views.InsuranceClaimViewSet)
# Nested routes for Bill-related resources
bill_router = DefaultRouter()
bill_router.register(r'items', api_views.BillItemViewSet, basename='bill-items')
bill_router.register(r'payments', api_views.PaymentViewSet, basename='bill-payments')

# Web (HTMX) view patterns
web_urlpatterns = [
    # Patient views
    path('patient/billing-history/', views.patient_billing_history, name='patient_billing_history'),
    path('patient/bill/<int:bill_id>/', views.patient_bill_detail, name='patient_bill_detail'),
    path('patient/bill/<int:bill_id>/pay/', views.process_payment, name='process_payment'),
    path('bill/<int:bill_id>/pdf/', views.bill_pdf, name='bill_pdf'),
	# Doctor views
    path('doctor/billing/', views.doctor_billing_summary, name='doctor_billing_summary'),
    path('doctor/billing/create/', views.doctor_create_bill, name='doctor_create_bill'),
    path('doctor/billing/create/<int:appointment_id>/', views.doctor_create_bill, name='doctor_create_bill_from_appointment'),
	 # Admin views
    path('admin/billing/', views.admin_billing_dashboard, name='admin_billing_dashboard'),
    path('admin/billing/payment/<int:bill_id>/', views.admin_record_payment, name='admin_record_payment'),
]
api_urlpatterns = [
    # Include router URLs
    path('api/', include(router.urls)),
    
    # Patient billing endpoints
    path('api/patient/me/bills/', api_views.PatientBillsView.as_view(), name='patient-bills'),
    path('api/bills/<int:pk>/', api_views.BillDetailView.as_view(), name='bill-detail'),
    path('api/bills/<int:pk>/download/', api_views.download_bill_pdf, name='download-bill-pdf'),
    
    # Payment endpoints
    path('api/bills/<int:pk>/pay_balance/', api_views.pay_bill_balance, name='pay-bill-balance'),
    path('api/appointments/payment/initiate/', api_views.initiate_appointment_payment, name='initiate-appointment-payment'),
    path('api/appointments/payment/confirm/', api_views.confirm_appointment_payment, name='confirm-appointment-payment'),
    path('api/appointments/invoice/generate/', api_views.generate_provisional_invoice, name='api_generate_provisional_invoice'),
    
    # Doctor billing endpoints
    path('api/doctor/me/billing-summary/', api_views.doctor_billing_summary, name='doctor-billing-summary'),
    path('api/appointments/invoice/generate/', api_views.generate_provisional_invoice, name='generate-provisional-invoice'),
    path('api/bills/<int:pk>/finalize/', api_views.finalize_invoice, name='finalize-invoice'),
    # Payment webhook
    path('api/payments/webhook/', api_views.payment_webhook, name='api_payment_webhook'),
	# Patient and Doctor summary views
    path('api/patient/me/bills/', api_views.patient_bills_api, name='api_patient_bills'),
    path('api/doctor/me/billing-summary/', api_views.doctor_billing_summary_api, name='api_doctor_billing_summary'),
    # Legacy views URLs
    path('', views.billing_home, name='billing-home'),
] 
# Combined URL patterns
urlpatterns = web_urlpatterns + api_urlpatterns 