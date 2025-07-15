from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import create_prescription_view
from .views.drugs_views import drug_suggestions
from .views import prescription_htmx_views
from .views import prescription_views

from .views import doctor_views, staff_views, admin_views, lab_views
from .views import auth_views
from .views import (
    signup_view,
    login_view,
    dashboard_view,
    appointments_view,
    logout_view,
    patients_view,
    create_patient,
    patients_list,
    patient_detail,
    patient_edit,
    create_appointment,
    patient_views,
    api_views,
    admin_views,
    pdf_views,
    billing_views,
    report_views,
    lab_views,
    lab_test_views,
)

from .views.drugs_views import (
    drug_suggestions,
    api_drug_suggestions,
)

from .views.template_views import (
    signup_view,
    profile_view,   
    profile_edit_view,
    logout_view,
    patients_view,
    create_patient,
    patient_detail,
    patient_edit,
    patient_form,
)
from users.views.doctor_views import (   
    DoctorCreateView,
    DoctorListView,
    DoctorDetailView,
    save_doctor,
    verify_doctor_api_view,
    
)
from .views.appointment_views import (
    AppointmentView,
    AppointmentListView,
    AppointmentCreateView,
    appointments_view,
    appointment_detail,
    appointment_delete,
    get_available_slots,
    update_appointment_status,
    appointment_edit,
)
from .views.patient_views import (
    create_patient,
    patients_list,
    patient_detail,
    patient_edit,
    patient_prescriptions,
    patient_dashboard,
    patient_create_appointment,
    prescription_detail,
    
)
from .views.prescription_views import (
    prescription_selection,
    prescription_detail,
    patient_prescriptions,
    prescriptions_view,
    PatientPrescriptionsView,
    CreatePrescriptionView,
    PrescriptionListView,
    prescription_detail_api,
    get_diagnosis_drug_suggestions,
)

from .views.clinic_admin_views import (
    clinic_admin_dashboard,
    clinic_profile,
    verify_doctor_credentials,
    add_doctor,
    doctors_list,
    delete_doctor,
    edit_doctor,
    add_staff,
    staff_list,
    edit_staff,
    toggle_staff_status,
    doctor_details,
    clinic_admin_dashboard_api,
    doctor_list_api,
    create_clinic_api,
    update_current_clinic,
    get_clinics_api,
    get_current_clinic,
    doctor_detail_api,
    add_lab,
    labs_list,
    lab_staff_list,
    lab_tests,
    assign_doctor,
    available_doctors,
    approve_staff_leave,
    reject_staff_leave,
    doctor_leaves,
    approve_doctor_leave,
    reject_doctor_leave,
)

from .views.auth_views import (
    
    login_api,
    logout_api,
    signup_api,
    doctor_signup_api,
    patient_signup_api,
    doctor_signup_view,
    patient_signup_view,
    verify_firebase_token,
)

from .views.api_views import (
    get_patient_appointments,
    get_doctors,
    get_clinic_appointments,
    get_clinic_doctors,
    get_clinic_staff,
    public_clinics_api,
    update_staff_role,
    get_available_slots,
    get_clinics,
    get_clinic_patients,
)

from .views import dashboard_views
from .views import appointment_views
from .views import clinic_admin_views
from clinic.views import clinic_reports

from .views.lab_views import LabTestViewSet
from .views.lab_management_views import LabManagementViewSet

app_name = 'users'

# API URLs
api_urlpatterns = [
    # JWT Token endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    path('appointments/', AppointmentView.as_view(), name='appointments_api'),
    path('appointments/list/', AppointmentListView.as_view(), name='appointments_list_api'),
    path('appointments/create/', AppointmentCreateView.as_view(), name='appointment_create_api'),
    path('prescriptions/patient/<int:patient_id>/', PatientPrescriptionsView.as_view(), name='doctor_patient_prescriptions_api'),
    path('prescriptions/<int:pk>/details/', prescription_detail_api, name='prescription_detail_api'),
    path('patients/prescriptions/<int:pk>/details/', prescription_detail_api, name='patient_prescription_detail_api'),
    path('prescriptions/mine/', PatientPrescriptionsView.as_view(), name='my_prescriptions_api'),
    path('prescriptions/create/', CreatePrescriptionView.as_view(), name='create_prescription_api'),
    path('drug-suggestions/', api_drug_suggestions, name='api_drug_suggestions'),
    path('diagnosis-suggestions/', get_diagnosis_drug_suggestions, name='diagnosis_drug_suggestions_api'),
]

# Set up REST API Router
router = DefaultRouter()
router.register(r'lab-tests', LabTestViewSet, basename='lab-test')
router.register(r'labs', LabManagementViewSet, basename='lab-management')

# Main URLs
urlpatterns = [
    # Authentication & Profile URLs
    path('', login_view, name='login'),
    path('login/', login_view, name='login'), 
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit_view, name='profile_edit_view'),
    path('profile/setup/', dashboard_views.profile_setup, name='profile_setup'),
    path('auth/google/', verify_firebase_token, name='verify_firebase_token'),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('accounts/', include('allauth.urls')),
    
    # Dashboard URLs
    path('dashboard/', dashboard_views.dashboard_redirect, name='dashboard'),
    path('doctor/dashboard/', doctor_views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    path('doctor/admin/dashboard/', dashboard_views.admin_dashboard, name='admin_dashboard'),
    path('clinic/admin/dashboard/', dashboard_views.admin_dashboard, name='clinic_admin_dashboard'),
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff_dashboard'),
    
    # Superuser URLs
    path('superuser/dashboard/', admin_views.superuser_dashboard, name='superuser_dashboard'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    
    # Patient URLs
    path('patients/create/', create_patient, name='create_patient'),
    path('patients/', patients_list, name='patients_list'),
    path('patients/list/', patients_list, name='get_patients'),
    path('patients/<int:patient_id>/', patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/edit/', patient_edit, name='patient_edit'),
    path('patients/form/', patient_form, name='patient_form'),
    path('patient_detail/<int:patient_id>/', patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/prescriptions/', patient_prescriptions, name='patient_prescriptions'),
    
    # Patient specific URLs
    path('patient/signup/', patient_signup_view, name='patient_signup'),
    path('patient/signup/api/', patient_signup_api, name='patient_signup_api'),
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    path('patient/prescriptions/', patient_views.patient_prescriptions, name='patient_prescriptions'),
    path('patient/medical-history/', patient_views.patient_medical_history, name='patient_medical_history'),
    path('patient/profile/', patient_views.patient_profile, name='patient_profile'),
    path('patient/create-appointment/', patient_views.patient_create_appointment, name='patient_create_appointment'),
    path('patient/test-results/', patient_views.patient_test_results, name='patient_test_results'),
    path('patient/health-records/', patient_views.patient_health_records, name='patient_health_records'),
    path('patient/appointments/', patient_views.patient_appointments, name='patient_appointments_list'),
    path('patient/lab-test/<int:pk>/', lab_views.patient_lab_test_detail, name='patient_lab_test_detail'),
    path('patient/billing/', billing_views.patient_billing_history, name='patient_billing_history'),
    path('patient/billing/<int:bill_id>/', billing_views.patient_bill_detail, name='patient_bill_detail'),
    path('patient/scheduling-dashboard/', patient_views.patient_scheduling_dashboard, name='patient_scheduling_dashboard'),
    path('patient/book-appointment-scheduling/', patient_views.patient_book_appointment_scheduling, name='patient_book_appointment_scheduling'),
    
    # Doctor URLs
    path('doctor/signup/', doctor_signup_view, name='doctor_signup'),
    path('doctor/signup/api/', doctor_signup_api, name='doctor_signup_api'),
    path('doctor/appointments/', doctor_views.doctor_appointments, name='doctor_appointments_view'),
    path('doctor/appointments/create/', doctor_views.doctor_create_appointment, name='doctor_create_appointment'),
    path('doctor/appointments/<uuid:appointment_id>/', doctor_views.appointment_detail_doctor, name='appointment_detail_doctor'),
    path('doctor/appointments/<uuid:appointment_id>/status/', doctor_views.update_appointment_status, name='update_appointment_status'),
    path('doctor/appointments/<uuid:appointment_id>/edit/', doctor_views.edit_appointment, name='edit_appointment'),
    path('doctor/appointments/<uuid:appointment_id>/attend/', doctor_views.attend_appointment, name='attend_appointment'),
    path('doctor/appointments/<uuid:appointment_id>/postpone/', doctor_views.postpone_appointment, name='postpone_appointment'),
    path('doctor/appointments/<uuid:appointment_id>/complete/', doctor_views.complete_appointment, name='complete_appointment'),
    path('doctor/appointments/<uuid:appointment_id>/actions/', doctor_views.appointment_actions, name='appointment_actions'),
    path('doctor/patients/', patient_views.patients_list, name='patients_list'),
    path('doctor/patients/create/', patient_views.create_patient, name='create_patient'),
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),
    path('doctor/patients/<int:patient_id>/edit/', patient_views.patient_edit, name='patient_edit'),
    path('doctor/patients/<int:patient_id>/vitals/', patient_views.patient_vitals_history, name='patient_vitals_history'),
    path('doctor/patients/<int:patient_id>/vitals/add/', patient_views.add_patient_vitals, name='add_patient_vitals'),
    path('doctor/profile/', doctor_views.doctor_profile, name='doctor_profile'),
    path('doctor/patients/<int:patient_id>/prescriptions/create/', create_prescription_view.create_prescription, name='create_prescription'),
    path('doctor/prescriptions/<int:pk>/', prescription_views.prescription_detail, name='prescription_detail_view'),
    path('doctor/patients/<int:patient_id>/prescriptions/', prescription_views.patient_prescriptions, name='patient_prescriptions'),
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),
    path('doctor/prescriptions/<int:pk>/pdf/', pdf_views.generate_prescription_pdf, name='prescription_pdf'),
    path('doctor/create-patient/', doctor_views.create_patient_doctor, name='create_patient_doctor'),
    path('doctor/availability/', doctor_views.manage_availability, name='manage_availability'),
    path('doctor/generate-slots/', doctor_views.generate_slots, name='generate_slots'),
    path('doctor/generate-slots-week/', doctor_views.generate_slots_for_week, name='generate_slots_for_week'),
    path('doctor/generate-single-date-slots/', doctor_views.generate_single_date_slots, name='generate_single_date_slots'),
    path('doctor/integrated-dashboard/', doctor_views.integrated_scheduling_dashboard, name='integrated_scheduling_dashboard'),
    path('doctor/sync-appointments/', doctor_views.sync_appointments_to_scheduling, name='sync_appointments_to_scheduling'),
    path('doctor/leaves/', doctor_views.manage_leaves, name='manage_leaves'),
    path('doctor/calendar/', doctor_views.doctor_calendar, name='doctor_calendar'),
    path('doctor/calendar/events/', doctor_views.doctor_calendar_events, name='doctor_calendar_events'),
    path('doctor/lab-tests/', lab_views.doctor_lab_tests, name='doctor_lab_tests'),
    path('doctor/lab-test/<int:pk>/', lab_views.doctor_lab_test_detail, name='doctor_lab_test_detail'), 
    path('doctor/billing/', billing_views.doctor_billing_summary, name='doctor_billing_summary'),
    path('doctor/billing/overview/', billing_views.doctor_billing_overview, name='doctor_billing_overview'),
    path('doctor/billing/create/', doctor_views.doctor_create_billing, name='doctor_create_billing'),
    path('doctor/billing/<int:billing_id>/', doctor_views.doctor_billing_detail, name='doctor_billing_detail'),
    path('doctor/report/overview/', report_views.doctor_report_overview, name='doctor_report_overview'),
    path('doctor/billing/create/<uuid:appointment_id>/', billing_views.create_bill, name='create_bill'),
    path('doctor/leaves/approve/<int:leave_id>/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('doctor/leaves/reject/<int:leave_id>/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    
    # Doctor related URLs
    path('doctors/create/', DoctorCreateView.as_view(), name='create_doctor'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/save/', save_doctor, name='save_doctor'),
    path('doctors/verify/', verify_doctor_api_view, name='verify_doctor'),
    path('doctors/appointments/create/', doctor_views.create_appointment, name='create_appointment'),
    path('doctors/appointments/doctor/<int:appointment_id>/', doctor_views.appointment_detail_doctor, name='appointment_detail_doctor'),
    path('doctors/verify/', api_views.verify_doctor, name='verify_doctor'),
    path('doctors/api/create/', api_views.create_doctor_profile, name='create_doctor_profile'),
    path('verify-doctor/', auth_views.verify_doctor_api, name='verify_doctor'),
    
    # Appointment URLs
    path('appointments/', appointments_view, name='appointments'),
    path('appointments/create/', create_appointment, name='create_appointment'),
    path('appointment/<uuid:pk>/', appointment_detail, name='appointment_detail'),
    path('appointment/<uuid:pk>/delete/', appointment_delete, name='appointment_delete'),
    path('appointments/<uuid:appointment_id>/update-status/', appointment_views.update_appointment_status, name='appointment_update_status'),
    path('appointments/<uuid:appointment_id>/delete/', appointment_views.appointment_delete, name='appointment_delete'),
    path('appointments/<uuid:appointment_id>/edit/', appointment_views.appointment_edit, name='appointment_edit'),
    
    # Staff URLs
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff_dashboard'),
    path('staff/appointments/', staff_views.staff_appointments, name='staff_appointments'),
    path('staff/calendar/', staff_views.staff_calendar, name='staff_calendar'),
    path('staff/calendar/events/', staff_views.staff_calendar_events, name='staff_calendar_events'),
    path('staff/patients/', staff_views.staff_patients, name='staff_patients'),
    path('staff/lab-tests/', staff_views.staff_lab_tests, name='staff_lab_tests'),
    path('staff/lab-tests/create/', staff_views.create_lab_test, name='staff_create_lab_test'),
    path('staff/billing/', staff_views.staff_billing, name='staff_billing'),
    path('staff/billing/overview/', staff_views.billing_overview, name='billing_overview'),
    path('staff/billing/create/', staff_views.staff_create_billing, name='staff_create_billing'),
    path('debug/staff-permissions/', staff_views.debug_staff_permissions, name='debug_staff_permissions'),
    path('staff/billing/<int:billing_id>/', staff_views.staff_billing_detail, name='staff_billing_detail'),
    path('staff/billing/<int:billing_id>/update/', staff_views.staff_update_billing, name='staff_update_billing'),
    path('staff/billing/<int:billing_id>/delete/', staff_views.staff_delete_billing, name='staff_delete_billing'),
    path('staff/appointments/create/', staff_views.staff_create_appointment, name='staff_create_appointment'),
    path('staff/appointments/<uuid:appointment_id>/update/', staff_views.staff_update_appointment, name='staff_update_appointment'),
    path('staff/appointments/<uuid:appointment_id>/cancel/', staff_views.staff_cancel_appointment, name='staff_cancel_appointment'),
    path('staff/appointments/<uuid:appointment_id>/', staff_views.staff_appointment_detail, name='staff_appointment_detail'),
    path('staff/patients/<int:patient_id>/', staff_views.staff_patient_detail, name='staff_patient_detail'),
    path('staff/lab-tests/<int:test_id>/', staff_views.staff_lab_test_detail, name='staff_lab_test_detail'),
    path('staff/lab-tests/<int:test_id>/update/', staff_views.staff_update_lab_test, name='staff_update_lab_test'),
    path('staff/lab-tests/<int:test_id>/delete/', staff_views.staff_delete_lab_test, name='staff_delete_lab_test'),
    path('staff/walk-in/', staff_views.staff_walk_in_appointment, name='staff_walk_in_appointment'),
    path('staff/leaves/', staff_views.staff_manage_leaves, name='staff_manage_leaves'),
    path('staff/leaves/approve/<int:leave_id>/', clinic_admin_views.approve_staff_leave, name='approve_staff_leave'),
    path('staff/leaves/reject/<int:leave_id>/', clinic_admin_views.reject_staff_leave, name='reject_staff_leave'),
    
    # Prescription URLs
    path('prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    path('prescriptions/list/', prescriptions_view, name='prescriptions_list'),
    path('prescriptions/patient/<int:patient_id>/', patient_prescriptions, name='patient_prescriptions'),
    path('prescriptions/', prescriptions_view, name='prescriptions'),
    path('patient/prescriptions/', PrescriptionListView.as_view(), name='patient_prescriptions_web'),
    
    # Clinic Admin URLs
    path('clinic-admin/', clinic_admin_dashboard, name='clinic_admin_dashboard'),
    path('clinic-admin/profile/', clinic_profile, name='clinic_profile'),
    path('clinic-admin/staff-leaves/', clinic_admin_views.staff_leaves, name='staff_leaves'),
    path('clinic-admin/doctor-leaves/', clinic_admin_views.doctor_leaves, name='doctor_leaves'),
    path('clinic-admin/staff-leaves/approve/<int:leave_id>/', clinic_admin_views.approve_staff_leave, name='approve_staff_leave'),
    path('clinic-admin/staff-leaves/reject/<int:leave_id>/', clinic_admin_views.reject_staff_leave, name='reject_staff_leave'),
    path('clinic-admin/doctor-leaves/approve/<int:leave_id>/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('clinic-admin/doctor-leaves/reject/<int:leave_id>/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    path('clinic-admin/doctors/', doctors_list, name='doctors_list'),
    path('clinic-admin/doctors/add/', add_doctor, name='add_doctor'),
    path('clinic-admin/doctors/verify/', verify_doctor_credentials, name='verify_doctor_credentials'),
    path('clinic-admin/doctors/<int:doctor_id>/edit/', edit_doctor, name='edit_doctor'),
    path('clinic-admin/doctors/<int:doctor_id>/delete/', delete_doctor, name='delete_doctor'),
    path('clinic-admin/doctors/assign/', assign_doctor, name='assign_doctor'),
    path('clinic-admin/doctors/available/', available_doctors, name='available_doctors'),
    path('clinic-admin/doctors/<int:doctor_id>/', doctor_details, name='doctor_details'),
    path('clinic-admin/doctors/<int:doctor_id>/details/', doctor_details, name='doctor_details'),
    path('clinic-admin/staff/', staff_list, name='staff_list'),
    path('clinic-admin/staff/add/', add_staff, name='add_staff'),
    path('clinic-admin/staff/credentials/', clinic_admin_views.staff_credentials, name='staff_credentials'),
    path('clinic-admin/staff/<int:staff_id>/edit/', edit_staff, name='edit_staff'),
    path('clinic-admin/staff/<int:staff_id>/toggle-status/', toggle_staff_status, name='toggle_staff_status'),
    path('clinic-admin/staff/appointments/create/', staff_views.staff_create_appointment, name='staff_create_appointment'),
    path('clinic-admin/dashboard/', clinic_admin_views.clinic_admin_dashboard_api, name='clinic_admin_dashboard_api'),
    path('clinic-admin/labs/', clinic_admin_views.labs_list, name='labs_list'),
    path('clinic-admin/labs/add/', clinic_admin_views.add_lab, name='add_lab'),
    path('clinic-admin/labs/staff/', clinic_admin_views.lab_staff_list, name='lab_staff_list'),
    path('clinic-admin/labs/tests/', clinic_admin_views.lab_tests, name='lab_tests'),
    path('clinic-admin/lab/dashboard/', lab_views.lab_dashboard, name='lab_dashboard'),
    path('clinic_admin/appointments/create/', appointment_views.admin_create_appointment, name='admin_create_appointment'),
    path('change-clinic/<int:clinic_id>/', clinic_admin_views.change_clinic, name='change_clinic'),
    path('edit-clinic-profile/<int:clinic_id>/', clinic_admin_views.edit_clinic_profile, name='edit_clinic_profile'),
    
    # Lab Test URLs
    path('lab-prescriptions/<int:prescription_id>/', lab_test_views.lab_prescription_detail, name='lab_prescription_detail'),
    path('lab-prescriptions/create/<int:patient_id>/', lab_test_views.create_lab_prescription, name='create_lab_prescription'),
    path('lab-tests/<int:pk>/detail/', lab_views.patient_lab_test_detail, name='patient_lab_test_detail'),
    path('lab-prescription/<int:prescription_id>/', lab_test_views.lab_prescription_detail, name='lab_prescription_detail'),
    path('book-lab-test/<int:prescription_id>/', lab_test_views.book_lab_test, name='book_lab_test'),
    path('lab-tests/<int:pk>/', lab_views.lab_test_detail, name='lab_test_detail'),
    path('lab-tests/<int:test_id>/update-status/', lab_views.update_lab_test_status, name='update_lab_test_status'),
    path('add-lab/', clinic_admin_views.add_lab, name='add_lab'),
    
    # Billing URLs
    path('billing/<int:billing_id>/', billing_views.billing_detail, name='billing_detail'),
    path('admin/billing/', billing_views.admin_billing_dashboard, name='admin_billing_dashboard'),
    path('admin/billing/payment/<int:bill_id>/', billing_views.record_payment, name='record_payment'),
    
    # Report URLs
    path('reports/monthly/', report_views.generate_report, name='monthly_report'),
    
    # Doctor leave management
    path('doctor-leaves/', clinic_admin_views.doctor_leaves, name='doctor_leaves'),
    path('doctor-leaves/<int:leave_id>/approve/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/reject/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/edit/', clinic_admin_views.edit_doctor_leave, name='edit_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/cancel/', clinic_admin_views.cancel_doctor_leave, name='cancel_doctor_leave'),
    path('request-leave/', doctor_views.request_leave, name='request_leave'),
    
    # API URLs
    path('api/', include(api_urlpatterns)),
    path('api/appointments/', api_views.appointment_list, name='api_appointments'),
    path('api/appointments/<uuid:appointment_id>/status/', api_views.update_appointment_status, name='api_update_appointment_status'),
    path('api/doctor/appointments/<uuid:appointment_id>/update-status/', appointment_views.update_appointment_status_api, name='update_appointment_status_api'),
    path('api/appointments/<uuid:appointment_id>/cancel/', api_views.cancel_appointment, name='cancel_appointment'),
    path('api/drug-suggestions/', drug_suggestions, name='drug_suggestions'),  # Drug suggestions API endpoint
    path('api/patients/prescriptions/', PatientPrescriptionsView.as_view(), name='apiPresc_patient_prescriptions'),
    path('api/patients/prescriptions/create/', CreatePrescriptionView.as_view(), name='create_prescription'),
    
    # Patient API endpoints
    path('api/patient/me/', api_views.patient_me, name='patient_me'),
    path('api/patients/prescriptions/', api_views.patient_prescriptions, name='apiviewpatient_prescriptions'),
    path('api/patient/appointments/', api_views.patient_appointments, name='patient_appointments'),
    path('api/patient/medical-history/', api_views.patient_medical_history_api, name='patient_medical_history_api'),
    
    # Doctor API endpoints
    path('api/doctor/me/', api_views.doctor_me, name='doctor_me'),
    path('api/doctor-dashboard/appointments/', api_views.doctor_appointments, name='doctor_appointments'),
    path('api/doctor/patients/', api_views.doctor_patients, name='doctor_patients'), 
    path('api/doctor/generate-slots/', doctor_views.generate_slots_api, name='generate_slots_api'),
    path('api/doctor/appointments/create/', doctor_views.api_create_appointment, name='api_create_appointment'),

    
    path('api/doctor/patient/<int:patient_id>/', doctor_views.api_patient_details, name='api_patient_details'),
    path('api/doctor/patient/<int:patient_id>/prescriptions/', doctor_views.api_patient_prescriptions, name='api_patient_prescriptions'),
    path('api/doctor/patient/<int:patient_id>/appointments/', doctor_views.api_patient_appointments, name='api_patient_appointments'),
    path('api/doctor/patients/<int:patient_id>/medical-history/', doctor_views.api_patient_medical_history, name='api_patient_medical_history'),
    path('api/doctor/patient/<int:patient_id>/', doctor_views.get_patient_details, name='get_patient_details'),

    path('api/doctor/appointments/<uuid:appointment_id>/', doctor_views.api_appointment_detail, name='api_appointment_detail'),
    path('api/doctor/prescriptions/<int:pk>/api/', prescription_views.prescription_detail_api, name='prescription_detail_api'),
    path('api/doctor/prescriptions/create/', doctor_views.create_prescription_api, name='create_prescription_api'),
    path('api/doctor/create-patient/', doctor_views.create_patient_api, name='create_patient_api'),
    path('api/doctor/profile/', doctor_views.doctor_profile_api, name='doctor_profile_api'),
    path('api/doctor/available-slots/<int:doctor_id>/<str:date>/', doctor_views.get_available_slots_doctor, name='get_available_slots_doctor'),
    path('api/doctor/day-status/<str:date>/', doctor_views.doctor_day_status, name='doctor_day_status'),
    path('api/doctor/dashboard/calendar-events/', doctor_views.doctor_dashboard_calendar_events, name='doctor_dashboard_calendar_events'),
    path('api/doctor/appointments/list/', doctor_views.doctor_appointments_api, name='doctor_appointments_api'),
    path('api/doctor/prescriptions/patient/<int:patient_id>/', doctor_views.patient_prescriptions_api, name='patient_prescriptions_api'),
    path('api/doctor/patients/<int:patient_id>/latest-vitals/', doctor_views.get_patient_latest_vitals, name='patient-latest-vitals'),
    
    # Slots API endpoints
    path('api/slots/available/', doctor_views.get_available_slots_api, name='get_available_slots_api'),
    path('api/available-slots/patient/<int:doctor_id>/<str:date>/', patient_views.get_available_slots_patient, name='get_available_slots_patient'),
    path('api/available-slots/doctor/<int:doctor_id>/<str:date>/', doctor_views.get_available_slots_doctor, name='get_available_slots_doctor'),
    path('api/appointments/available-slots/<int:doctor_id>/<str:date>/', get_available_slots, name='get_available_slots'),
    
    # Clinic Profile endpoints
    path('api/clinic/profile/', api_views.clinic_profile_api, name='clinic_profile_api'),
    path('api/clinic-admin/dashboard-stats/', clinic_admin_views.dashboard_stats, name='dashboard_stats'),
    path('api/clinic-admin/doctors/', clinic_admin_views.doctor_list_api, name='doctor_list_api'),
    path('api/clinic-admin/doctors/<int:clinic_id>/', clinic_admin_views.doctor_list_api, name='doctor_list_api_with_id'),
    path('api/clinic-admin/dashboard/<int:clinic_id>/', clinic_admin_views.clinic_admin_dashboard_api, name='clinic_admin_dashboard_api_with_id'),
    path('api/clinics/current/', clinic_admin_views.get_current_clinic, name='get_current_clinic'),
    path('api/clinic-admin/patients/', clinic_admin_views.patient_list_api, name='patient_list_api'),
    path('api/clinic-admin/patients/<int:clinic_id>/', clinic_admin_views.patient_list_api, name='patient_list_api_with_id'),
    path('api/clinic-admin/doctors/<int:doctor_id>/', clinic_admin_views.edit_doctor_api, name='edit_doctor_api'),
    path('api/clinic-admin/doctors/<int:doctor_id>/detail/', clinic_admin_views.doctor_detail_api, name='doctor_detail_api'),
    path('api/clinic-admin/doctors/<int:doctor_id>/status/', clinic_admin_views.doctor_status_api, name='doctor_status_api'),
    path('api/clinic-admin/clinics/', get_clinics, name='get_clinics'),
    path('api/clinic-admin/patients/list/<int:clinic_id>/', get_clinic_patients, name='get_clinic_patients'),
    path('api/clinic-admin/doctors/<int:clinic_id>/', api_views.clinic_doctors, name='clinic_doctors'),
    
    # Superuser Admin endpoints
    path('api/admin/clinics/', api_views.admin_clinics_api, name='admin_clinics_api'),
    path('api/admin/clinics/<int:clinic_id>/doctors/', api_views.admin_doctors_api, name='admin_doctors_api'),
    path('api/admin/clinics/<int:clinic_id>/staff/', api_views.admin_staff_api, name='admin_staff_api'),
    path('api/admin/clinics/<int:clinic_id>/appointments/', api_views.clinic_appointments_api, name='clinic_appointments_api'),
    path('api/get-csrf-token/', api_views.get_csrf_token, name='get_csrf_token'),
    path('admin/clinics/<int:clinic_id>/staff/<int:staff_id>/role/', update_staff_role, name='update_staff_role'),
    path('api/admin/patient-edit/<int:patient_id>/', api_views.edit_patient_details, name='edit_patient_details'),
    path('api/admin/patient-update/<int:patient_id>/', api_views.update_patient_details, name='update_patient_details'),
    
    # Authentication API endpoints
    path('api/auth/login/', auth_views.login_api, name='login_api'),
     
    # Clinic API endpoints
    path('api/clinics/', get_clinics_api, name='get_clinics_api'),
    path('api/clinics/public/', public_clinics_api, name='public_clinics_api'),
    path('api/clinics/create/', create_clinic_api, name='create_clinic_api'),
    path('api/clinics/current/', update_current_clinic, name='update_current_clinic'),
    
    # Appointment API endpoints
    path('api/appointments/create/', api_views.create_appointment, name='create_appointment'),
    path('api/appointments/calendar/', staff_views.staff_calendar_events, name='staff_calendar_events'),
    
    # Labs API endpoints
    path('api/labs/available/', lab_views.get_available_labs, name='get_available_labs'),
    
    # Drug API endpoints
    path('api/drugs/suggestions/', api_drug_suggestions, name='api_drug_suggestions'),
    
    # Add new API endpoints for React Native
    path('users/doctor/dashboard/', api_views.doctor_dashboard_api, name='doctor_dashboard_api'),
    path('users/doctor/patients/', api_views.doctor_patients_api, name='doctor_patients_api'),
    path('users/patient/<int:patient_id>/', api_views.patient_detail_api, name='patient_detail_api'),
    path('users/patient/<int:patient_id>/records/', api_views.patient_records_api, name='patient_records_api'),
    path('users/doctor/appointments/<uuid:appointment_id>/actions/', api_views.appointment_actions_api, name='appointment_actions_api'),
    
    # React Native specific API endpoints
    path('api/doctor/appointments/list/', doctor_views.doctor_appointments_api, name='rn_doctor_appointments_api'),
    path('api/doctor/patients/', api_views.doctor_patients_api, name='rn_doctor_patients_api'),
    path('api/doctor/dashboard/', api_views.doctor_dashboard_api, name='rn_doctor_dashboard_api'),
    
    # Additional endpoints for React Native compatibility
    path('api/doctor/appointments/<uuid:appointment_id>/', doctor_views.api_appointment_detail, name='api_appointment_detail'),
    path('api/doctor/appointments/<uuid:appointment_id>/update-status/', appointment_views.update_appointment_status_api, name='update_appointment_status_api'),
    path('api/doctor/prescriptions/patient/<int:patient_id>/', doctor_views.patient_prescriptions_api, name='patient_prescriptions_api'),
    
    # Patient-related API endpoints
    path('api/patient/<int:patient_id>/vitals/', api_views.patient_vitals_api, name='patient_vitals_api'),
    path('api/patient/<int:patient_id>/records/', api_views.patient_records_api, name='patient_records_api'),
    path('api/test-results/<int:test_id>/', api_views.test_results_api, name='test_results_api'),
    #path('api/prescriptions/<int:prescription_id>/', api_views.prescription_detail_api, name='prescription_detail_api'),
    
    # Add these new URL patterns for modern prescription features
    path('api/diagnosis/suggestions/', prescription_htmx_views.diagnosis_suggestions, name='diagnosis_suggestions'),
    path('api/medicine/suggestions/', prescription_htmx_views.medicine_suggestions, name='medicine_suggestions'),
    path('api/medicine/details/', prescription_htmx_views.medicine_details, name='medicine_details'),
    path('api/quick-add/content/', prescription_htmx_views.quick_add_content, name='quick_add_content'),
    path('api/lab-test/panel/', prescription_htmx_views.lab_test_panel, name='lab_test_panel'),
    path('api/templates/recent/', prescription_htmx_views.recent_templates, name='recent_templates'),
    path('api/templates/save/', prescription_htmx_views.save_template, name='save_template'),
    path('api/templates/<int:template_id>/', prescription_htmx_views.load_template, name='load_template'),
    path('api/prescription/draft/save/', prescription_htmx_views.save_prescription_draft, name='save_prescription_draft'),
    path('api/medicines/search/', prescription_htmx_views.search_medicines, name='search_medicines'),
    path('api/patient/<int:patient_id>/history/', prescription_htmx_views.patient_history, name='patient_history'),
    path('api/patient/<int:patient_id>/vitals/modal/', prescription_htmx_views.update_vitals_modal, name='update_vitals_modal'),

    # New prescription creation routes
    path('prescription/selection/<int:patient_id>/', prescription_views.prescription_selection, name='prescription_selection'),
    path('prescription/create/modern/<int:patient_id>/', prescription_views.create_prescription_modern, name='create_prescription_modern'),

    # Prescription item management routes
    path('prescription/<int:prescription_id>/item/<int:item_id>/delete/', prescription_views.delete_prescription_item, name='delete_prescription_item'),
    path('prescription/<int:prescription_id>/item/<int:item_id>/edit/', prescription_views.edit_prescription_item, name='edit_prescription_item'),
    path('prescription/<int:prescription_id>/lab-test/<int:lab_test_id>/delete/', prescription_views.delete_lab_test, name='delete_lab_test'),
    path('prescription/<int:prescription_id>/lab-test/<int:lab_test_id>/edit/', prescription_views.edit_lab_test, name='edit_lab_test'),

    # Register the router URLs
    path('api/', include(router.urls)),
]
