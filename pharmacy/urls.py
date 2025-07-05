from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

app_name = 'pharmacy'

router = DefaultRouter()
router.register(r'pharmacies', api_views.PharmacyViewSet)

urlpatterns = [
    # Include router URLs
    path('api/', include(router.urls)),
    
    # Patient prescription endpoints
    path('api/patient/me/prescriptions/', api_views.PatientPrescriptionsView.as_view(), name='patient-prescriptions'),
    path('api/prescriptions/<int:pk>/', api_views.PrescriptionDetailView.as_view(), name='prescription-detail'),
    
    # Pharmacy availability and delivery
    path('api/pharmacies/<int:pharmacy_id>/check-availability/<int:medicine_id>/', 
         api_views.check_medicine_availability, name='check-medicine-availability'),
    path('api/delivery/request/', api_views.request_medication_delivery, name='request-medication-delivery'),
    
    # Staff endpoints
    path('api/staff/dashboard/', api_views.StaffDashboardView.as_view(), name='staff-dashboard'),
    path('api/staff/inventory/', api_views.StaffInventoryView.as_view(), name='staff-inventory'),
    path('api/staff/prescriptions/pending/', api_views.PendingPrescriptionsView.as_view(), name='pending-prescriptions'),
    path('api/staff/prescriptions/<int:prescription_id>/process/', 
         api_views.process_prescription, name='process-prescription'),
] 