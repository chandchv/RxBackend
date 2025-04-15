from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import doctor_views, staff_views, admin_views, lab_views
from .views import auth_views
from .views import (
    signup_view,
    login_view,
    dashboard_view,
    appointments_view,
    profile_view,
    logout_view,
    patients_view,
    create_patient,
    patients_list,
    patient_detail,
    patient_edit,
    create_appointment,
    doctor_views,
    patient_views,
    prescription_views,
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
    create_prescription,
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
    
    path('appointments/', AppointmentView.as_view(), name='appointments_api'),
    path('appointments/list/', AppointmentListView.as_view(), name='appointments_list_api'),
    path('appointments/create/', AppointmentCreateView.as_view(), name='appointment_create_api'),
    path('prescriptions/patient/<int:patient_id>/', PatientPrescriptionsView.as_view(), name='doctor_patient_prescriptions_api'),
    path('prescriptions/<int:pk>/details/', prescription_detail_api, name='prescription_detail_api'),
    path('prescriptions/mine/', PatientPrescriptionsView.as_view(), name='my_prescriptions_api'),
    path('prescriptions/create/', CreatePrescriptionView.as_view(), name='create_prescription_api'),
    path('drug-suggestions/', api_drug_suggestions, name='api_drug_suggestions'),
    path('diagnosis-suggestions/', get_diagnosis_drug_suggestions, name='diagnosis_drug_suggestions_api'),
]

# Main URLs
urlpatterns = [
    # Superuser URLs
    path('superuser/dashboard/', admin_views.superuser_dashboard, name='superuser_dashboard'),
    
    # Patient URLs
    path('patients/create/', create_patient, name='create_patient'),
    path('patients/', patients_list, name='patients_list'),
    path('patients/list/', patients_list, name='get_patients'),
    path('patients/<int:patient_id>/', patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/edit/', patient_edit, name='patient_edit'),
    path('patients/form/', patient_form, name='patient_form'),
    path('patient_detail/<int:patient_id>/', patient_detail, name='patient_detail'),
    
    # Lab Test URLs
    path('lab-prescriptions/<int:prescription_id>/', lab_test_views.lab_prescription_detail, name='lab_prescription_detail'),
    path('lab-prescriptions/create/<int:patient_id>/', lab_test_views.create_lab_prescription, name='create_lab_prescription'),
    path('lab-tests/<int:pk>/detail/', lab_views.patient_lab_test_detail, name='patient_lab_test_detail'),
    
    # Appointment URLs
    path('appointments/', appointments_view, name='appointments'),
    path('appointments/create/', create_appointment, name='create_appointment'),
    path('appointment/<int:pk>/', AppointmentView.as_view(), name='appointment_detail'),
    path('appointment/<int:pk>/delete/', appointment_delete, name='appointment_delete'),
    
    # Staff URLs
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff_dashboard'),
    path('staff/appointments/', staff_views.staff_appointments, name='staff_appointments'),
    path('staff/calendar/', staff_views.staff_calendar_events, name='staff_calendar_events'),
    path('staff/patients/', staff_views.staff_patients, name='staff_patients'),
    path('staff/lab-tests/', staff_views.staff_lab_tests, name='staff_lab_tests'),
    path('staff/lab-tests/create/', staff_views.create_lab_test, name='staff_create_lab_test'),
    path('staff/billing/', staff_views.staff_billing, name='staff_billing'),
    path('staff/billing/create/', staff_views.create_billing, name='staff_create_billing'),
    path('staff/billing/<int:billing_id>/', staff_views.staff_billing_detail, name='staff_billing_detail'),
    path('staff/billing/<int:billing_id>/update/', staff_views.staff_update_billing, name='staff_update_billing'),
    path('staff/billing/<int:billing_id>/delete/', staff_views.staff_delete_billing, name='staff_delete_billing'),
    path('staff/appointments/create/', staff_views.staff_create_appointment, name='staff_create_appointment'),
    path('staff/appointments/<int:appointment_id>/update/', staff_views.staff_update_appointment, name='staff_update_appointment'),
    path('staff/appointments/<int:appointment_id>/cancel/', staff_views.staff_cancel_appointment, name='staff_cancel_appointment'),
    path('staff/appointments/<int:appointment_id>/', staff_views.staff_appointment_detail, name='staff_appointment_detail'),
    path('staff/patients/<int:patient_id>/', staff_views.staff_patient_detail, name='staff_patient_detail'),
    path('staff/lab-tests/<int:test_id>/', staff_views.staff_lab_test_detail, name='staff_lab_test_detail'),
    path('staff/lab-tests/<int:test_id>/update/', staff_views.staff_update_lab_test, name='staff_update_lab_test'),
    path('staff/lab-tests/<int:test_id>/delete/', staff_views.staff_delete_lab_test, name='staff_delete_lab_test'),
    path('staff/walk-in/', staff_views.staff_walk_in_appointment, name='staff_walk_in_appointment'),
    path('staff/leaves/', staff_views.staff_manage_leaves, name='staff_manage_leaves'),
    path('staff/leaves/approve/<int:leave_id>/', clinic_admin_views.approve_staff_leave, name='approve_staff_leave'),
    path('staff/leaves/reject/<int:leave_id>/', clinic_admin_views.reject_staff_leave, name='reject_staff_leave'),
    
    # Authentication & Profile URLs
    path('', login_view, name='login'),
    path('login/', login_view, name='login'), 
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'), 
    
    # Dashboard URLs
    path('doctor/dashboard/', dashboard_views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    path('doctor/admin/dashboard/', dashboard_views.admin_dashboard, name='admin_dashboard'),
    path('clinic/admin/dashboard/', dashboard_views.admin_dashboard, name='clinic_admin_dashboard'),
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff_dashboard'),
    path('dashboard/', dashboard_views.dashboard_redirect, name='dashboard'),

    #Prescription URLs
    path('prescriptions/create/', create_prescription, name='create_prescription'),
    path('prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    path('api/doctor/prescriptions/<int:pk>/api/', prescription_views.prescription_detail_api, name='prescription_detail_api'),
    path('prescriptions/list/', prescriptions_view, name='prescriptions_list'),
    path('prescriptions/patient/<int:patient_id>/', patient_prescriptions, name='patient_prescriptions'),
    path('prescriptions/', prescriptions_view, name='prescriptions'),
    path('prescriptions/create/<int:patient_id>/', create_prescription, name='create_prescription'),
    path('prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    
    path('patients/<int:patient_id>/prescriptions/', patient_prescriptions, name='patient_prescriptions'),
   
    # API URLs
     path('api/', include(api_urlpatterns)),

   
    # Clinic Admin URLs - Updated paths
    path('clinic-admin/', clinic_admin_dashboard, name='clinic_admin_dashboard'),
    path('clinic-admin/profile/', clinic_profile, name='clinic_profile'),
    path('clinic-admin/staff-leaves/', clinic_admin_views.staff_leaves, name='staff_leaves'),
    path('clinic-admin/doctor-leaves/', clinic_admin_views.doctor_leaves, name='doctor_leaves'),
    path('clinic-admin/staff-leaves/approve/<int:leave_id>/', clinic_admin_views.approve_staff_leave, name='approve_staff_leave'),
    path('clinic-admin/staff-leaves/reject/<int:leave_id>/', clinic_admin_views.reject_staff_leave, name='reject_staff_leave'),
    path('clinic-admin/doctor-leaves/approve/<int:leave_id>/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('clinic-admin/doctor-leaves/reject/<int:leave_id>/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    
    # Doctor management
    path('clinic-admin/doctors/', doctors_list, name='doctors_list'),
    path('clinic-admin/doctors/add/', add_doctor, name='add_doctor'),
    path('clinic-admin/doctors/verify/', verify_doctor_credentials, name='verify_doctor_credentials'),
    path('clinic-admin/doctors/<int:doctor_id>/edit/', edit_doctor, name='edit_doctor'),
    path('clinic-admin/doctors/<int:doctor_id>/delete/', delete_doctor, name='delete_doctor'),
    path('clinic-admin/doctors/assign/', assign_doctor, name='assign_doctor'),
    path('clinic-admin/doctors/available/', available_doctors, name='available_doctors'),
    path('clinic-admin/doctors/<int:doctor_id>/', doctor_details, name='doctor_details'),
    path('clinic-admin/doctors/<int:doctor_id>/details/', doctor_details, name='doctor_details'),
    path('clinic-admin/doctors/<int:doctor_id>/edit/', edit_doctor, name='edit_doctor'),
    path('clinic-admin/doctors/<int:doctor_id>/delete/', delete_doctor, name='delete_doctor'),
    path('clinic-admin/staff/appointments/create/', staff_views.staff_create_appointment, name='staff_create_appointment'),

    # Staff management
    path('clinic-admin/staff/', staff_list, name='staff_list'),
    path('clinic-admin/staff/add/', add_staff, name='add_staff'),
    path('clinic-admin/staff/credentials/', clinic_admin_views.staff_credentials, name='staff_credentials'),
    path('clinic-admin/staff/<int:staff_id>/edit/', edit_staff, name='edit_staff'),
    path('clinic-admin/staff/<int:staff_id>/toggle-status/', toggle_staff_status, name='toggle_staff_status'),

    # Doctor URLs
    path('doctor/appointments/', doctor_views.doctor_appointments_view, name='doctor_appointments_view'),
    path('doctor/appointments/create/', doctor_views.doctor_create_appointment, name='doctor_create_appointment'),
    path('doctor/signup/', doctor_signup_view, name='doctor_signup'),
    path('doctor/signup/api/', doctor_signup_api, name='doctor_signup_api'),
    path('doctor/patients/', patient_views.patients_list, name='patients_list'),
    path('doctor/patients/create/', patient_views.create_patient, name='create_patient'),
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),
    path('doctor/patients/<int:patient_id>/edit/', patient_views.patient_edit, name='patient_edit'),
    path('doctor/profile/', doctor_views.doctor_profile, name='doctor_profile'),

     # Doctor URLs
    
    #path('doctors/', DoctorListView.as_view(), name='doctors_list'),
    path('doctors/create/', DoctorCreateView.as_view(), name='create_doctor'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/save/', save_doctor, name='save_doctor'),
    path('doctors/verify/', verify_doctor_api_view, name='verify_doctor'),
    
    path('doctors/appointments/create/', doctor_views.create_appointment, name='create_appointment'),
    path('doctors/appointments/doctor/<int:appointment_id>/', doctor_views.appointment_detail_doctor, name='appointment_detail_doctor'),

    
    # Patient URLs
    path('patient/signup/', patient_signup_view, name='patient_signup'),
    path('patient/signup/api/', patient_signup_api, name='patient_signup_api'),
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    path('patient/prescriptions/', patient_prescriptions, name='patient_prescriptions'),  
    path('patient/prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    path('patient/appointments/create/', patient_views.patient_create_appointment, name='patient_create_appointment'),
    path('patient/profile/', patient_views.patient_profile, name='patient_profile'),
    
    
    # Prescription URLs
    path('doctor/patients/<int:patient_id>/prescriptions/create/', 
         prescription_views.create_prescription, name='create_prescription'),
    path('doctor/prescriptions/<int:pk>/', 
            prescription_views.prescription_detail, 
            name='prescription_detail'),
    path('doctor/patients/<int:patient_id>/prescriptions/', 
         prescription_views.patient_prescriptions, name='patient_prescriptions'),
    
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),
    path('doctor/prescriptions/<int:pk>/pdf/', pdf_views.generate_prescription_pdf, name='prescription_pdf'),
    # Authentication URLs
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # API URLs
    path('api/appointments/', api_views.appointment_list, name='api_appointments'),
    path('api/appointments/<int:appointment_id>/status/', 
         api_views.update_appointment_status, name='api_update_appointment_status'),
    path('api/doctor/appointments/<int:appointment_id>/update-status/', appointment_views.update_appointment_status_api, name='update_appointment_status_api'),
    
    # Default dashboard
    #path('dashboard/', doctor_views.doctor_dashboard, name='dashboard'),
    
    # Add to your urlpatterns
    path('patient/appointments/create/', patient_views.patient_create_appointment, name='patient_create_appointment'),
    
    path('api/appointments/<int:appointment_id>/cancel/', api_views.cancel_appointment, name='cancel_appointment'),
    
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('api/drug-suggestions/', drug_suggestions, name='drug_suggestions'),
    path('api/patients/prescriptions/', PatientPrescriptionsView.as_view(), name='apiPresc_patient_prescriptions'),
    path('api/patients/prescriptions/create/', CreatePrescriptionView.as_view(), name='create_prescription'),
    path('patient/prescriptions/', PrescriptionListView.as_view(), name='patient_prescriptions_web'),
    
    # Patient API endpoints
    path('api/patient/me/', api_views.patient_me, name='patient_me'),
    path('api/patients/prescriptions/', api_views.patient_prescriptions, name='apiviewpatient_prescriptions'),
    
    # Doctor API endpoints
    path('api/doctor/me/', api_views.doctor_me, name='doctor_me'),
    path('api/doctor-dashboard/appointments/', api_views.doctor_appointments, name='doctor_appointments'),
    
    # Patient API endpoints
    path('api/patient/appointments/', api_views.patient_appointments, name='patient_appointments'),
    
    # Clinic Profile endpoints
    path('api/clinic/profile/', api_views.clinic_profile_api, name='clinic_profile_api'),
    path('api/clinic-admin/dashboard-stats/', clinic_admin_views.dashboard_stats, name='dashboard_stats'),
    
    # Superuser Admin endpoints
    path('api/admin/clinics/', api_views.admin_clinics_api, name='admin_clinics_api'),
    path('api/admin/clinics/<int:clinic_id>/doctors/', api_views.admin_doctors_api, name='admin_doctors_api'),
    path('api/admin/clinics/<int:clinic_id>/staff/', api_views.admin_staff_api, name='admin_staff_api'),
    path('api/admin/clinics/<int:clinic_id>/appointments/', api_views.clinic_appointments_api, name='clinic_appointments_api'),
    path('api/get-csrf-token/', api_views.get_csrf_token, name='get_csrf_token'),
    path('doctors/verify/', api_views.verify_doctor, name='verify_doctor'),
    path('doctors/api/create/', api_views.create_doctor_profile, name='create_doctor_profile'),
    path('verify-doctor/', auth_views.verify_doctor_api, name='verify_doctor'),
    path('api/doctor/patients/', api_views.doctor_patients, name='doctor_patients'),
    path('doctor/create-patient/', doctor_views.create_patient_doctor, name='create_patient_doctor'),
    path('doctor/availability/', doctor_views.manage_availability, name='manage_availability'),
    path('doctor/generate-slots/', doctor_views.generate_slots, name='generate_slots'),
    path('api/doctor/generate-slots/', doctor_views.generate_slots_api, name='generate_slots_api'),
    path('doctor/leaves/', doctor_views.manage_leaves, name='manage_leaves'),
    path('doctor/leaves/approve/<int:leave_id>/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('doctor/leaves/reject/<int:leave_id>/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    path('profile/setup/', dashboard_views.profile_setup, name='profile_setup'),
    path('patient/medical-history/', 
         patient_views.patient_medical_history, 
         name='patient_medical_history'),
    path('api/patient/medical-history/', api_views.patient_medical_history_api, name='patient_medical_history_api'),
    path('billing/<int:billing_id>/', billing_views.billing_detail, name='billing_detail'),
    path('reports/monthly/', report_views.generate_report, name='monthly_report'),
    path('doctor/billing/', doctor_views.billing_overview, name='doctor_billing_overview'),
    path('doctor/reports/', doctor_views.report_overview, name='doctor_report_overview'),
    path('staff/billing/', staff_views.billing_overview, name='staff_billing_overview'),
    path('admin/billing/', admin_views.billing_overview, name='admin_billing_overview'),
    path('clinic_admin/appointments/create/', appointment_views.admin_create_appointment, name='admin_create_appointment'),
    #path('appointments/<int:appointment_id>/update-status/', appointment_views.update_appointment_status, 
         #name='update_appointment_status'),
    #path('appointments/<int:appointment_id>/', appointment_views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:appointment_id>/update-status/', appointment_views.update_appointment_status, name='appointment_update_status'),
    path('appointments/<int:appointment_id>/delete/', appointment_views.appointment_delete, name='appointment_delete'),
    path('appointments/<int:appointment_id>/edit/', appointment_views.appointment_edit, name='appointment_edit'),
    path('api/available-slots/patient/<int:doctor_id>/<str:date>/', 
         patient_views.get_available_slots_patient, 
         name='get_available_slots_patient'),
    path('api/available-slots/doctor/<int:doctor_id>/<str:date>/', 
            doctor_views.get_available_slots_doctor, 
         name='get_available_slots_doctor'),

    path('doctor/appointments/create/', doctor_views.create_appointment, name='create_appointment'),
    path('doctor/appointments/<int:appointment_id>/status/', doctor_views.update_appointment_status, name='update_appointment_status'),
    path('doctor/appointments/<int:appointment_id>/edit/', doctor_views.edit_appointment, name='edit_appointment'),
    
    # Patient billing URLs
    path('patient/billing/', billing_views.patient_billing_history, name='patient_billing_history'),
    path('patient/billing/<int:bill_id>/', billing_views.patient_bill_detail, name='patient_bill_detail'),
    
    # Doctor billing URLs
    path('doctor/billing/', billing_views.doctor_billing_summary, name='doctor_billing_summary'),
    path('doctor/billing/create/<int:appointment_id>/', billing_views.create_bill, name='create_bill'),
    
    # Admin billing URLs
    path('admin/billing/', billing_views.admin_billing_dashboard, name='admin_billing_dashboard'),
    path('admin/billing/payment/<int:bill_id>/', billing_views.record_payment, name='record_payment'),
    #path('api/doctor/appointments/create/', api_views.create_appointment, name='create-appointment'),
    path('api/doctor/appointments/create/', doctor_views.api_create_appointment, name='api_create_appointment'),

    # API endpoints for patient details
    path('api/doctor/patients/<int:patient_id>/', doctor_views.api_patient_details, name='api_patient_details'),
    path('api/doctor/patients/<int:patient_id>/prescriptions/', doctor_views.api_patient_prescriptions, name='api_patient_prescriptions'),
    path('api/doctor/patients/<int:patient_id>/appointments/', doctor_views.api_patient_appointments, name='api_patient_appointments'),
    path('api/doctor/patients/<int:patient_id>/medical-history/', doctor_views.api_patient_medical_history, name='api_patient_medical_history'),
 
    # Add this URL pattern
    path('api/doctor/patient/<int:patient_id>/', doctor_views.get_patient_details, name='get_patient_details'),

    path('api/doctor/appointments/<int:appointment_id>/', doctor_views.api_appointment_detail, name='api_appointment_detail'),

    # Add this to your urlpatterns
    path('api/drugs/suggestions/', api_drug_suggestions, name='api_drug_suggestions'),

    path('api/doctor/prescriptions/create/', doctor_views.create_prescription_api, name='create_prescription_api'),
    path('api/auth/login/', auth_views.login_api, name='login_api'),
    path('clinic-admin/dashboard/', clinic_admin_views.clinic_admin_dashboard_api, name='clinic_admin_dashboard_api'),
    path('api/clinic-admin/doctors/', clinic_admin_views.doctor_list_api, name='doctor_list_api'),
    path('api/clinic-admin/doctors/<int:clinic_id>/', clinic_admin_views.doctor_list_api, name='doctor_list_api_with_id'),
    path('change-clinic/<int:clinic_id>/', clinic_admin_views.change_clinic, name='change_clinic'),
    path('edit-clinic-profile/<int:clinic_id>/', clinic_admin_views.edit_clinic_profile, name='edit_clinic_profile'),
    path('api/clinics/', get_clinics_api, name='get_clinics_api'),
    path('api/clinics/public/', public_clinics_api, name='public_clinics_api'),
    path('api/clinics/create/', create_clinic_api, name='create_clinic_api'),
    path('api/clinics/current/', update_current_clinic, name='update_current_clinic'),
    path('api/clinic-admin/dashboard/<int:clinic_id>/', clinic_admin_views.clinic_admin_dashboard_api, name='clinic_admin_dashboard_api_with_id'),
    path('api/clinics/current/', clinic_admin_views.get_current_clinic, name='get_current_clinic'),
    path('api/clinic-admin/patients/', clinic_admin_views.patient_list_api, name='patient_list_api'),
    path('api/clinic-admin/patients/<int:clinic_id>/', clinic_admin_views.patient_list_api, name='patient_list_api_with_id'),
    path('api/clinic-admin/doctors/<int:doctor_id>/', clinic_admin_views.edit_doctor_api, name='edit_doctor_api'),
    path('api/clinic-admin/doctors/<int:doctor_id>/detail/', 
         clinic_admin_views.doctor_detail_api, 
         name='doctor_detail_api'),
    path('api/clinic-admin/doctors/<int:doctor_id>/status/', 
         clinic_admin_views.doctor_status_api, 
         name='doctor_status_api'),
    path('api/doctor/create-patient/', doctor_views.create_patient_api, name='create_patient_api'),
    path('api/doctor/profile/', doctor_views.doctor_profile_api, name='doctor_profile_api'),
    path('api/doctor/available-slots/', doctor_views.get_available_slots_doctor, name='get_available_slots_doctor'),
    path('api/doctor/appointments/list/', doctor_views.doctor_appointments_api, name='doctor_appointments_api'),
    path('api/doctor/prescriptions/patient/<int:patient_id>/', doctor_views.patient_prescriptions_api, name='patient_prescriptions_api'),
    path('admin/clinics/<int:clinic_id>/staff/<int:staff_id>/role/', update_staff_role, name='update_staff_role'),
    path('api/appointments/available-slots/<int:doctor_id>/<str:date>/', get_available_slots, name='get_available_slots'),
    path('api/appointments/create/', api_views.create_appointment, name='create_appointment'),
    path('api/clinic-admin/clinics/', get_clinics, name='get_clinics'),
    path('api/clinic-admin/patients/list/<int:clinic_id>/', get_clinic_patients, name='get_clinic_patients'),
    path('api/admin/patient-edit/<int:patient_id>/', api_views.edit_patient_details, name='edit_patient_details'),
    path('api/admin/patient-update/<int:patient_id>/', api_views.update_patient_details, name='update_patient_details'),
    path('api/clinic-admin/doctors/<int:clinic_id>/', api_views.clinic_doctors, name='clinic_doctors'),
    path(
        'api/doctor/patients/<int:patient_id>/latest-vitals/',
        doctor_views.get_patient_latest_vitals,
        name='patient-latest-vitals'
    ),
    path('auth/google/', verify_firebase_token, name='verify_firebase_token'),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('add-lab/', clinic_admin_views.add_lab, name='add_lab'),
    path('clinic-admin/labs/', clinic_admin_views.labs_list, name='labs_list'),
    path('clinic-admin/labs/add/', clinic_admin_views.add_lab, name='add_lab'),
    path('clinic-admin/labs/staff/', clinic_admin_views.lab_staff_list, name='lab_staff_list'),
    path('clinic-admin/labs/tests/', clinic_admin_views.lab_tests, name='lab_tests'),
    path('clinic-admin/lab/dashboard/', lab_views.lab_dashboard, name='lab_dashboard'),
    # LabTest URLs
    path('lab-tests/<int:pk>/', lab_views.lab_test_detail, name='lab_test_detail'),
    path('lab-tests/<int:test_id>/update-status/', lab_views.update_lab_test_status, name='update_lab_test_status'),
    path('doctor/lab-test/<int:pk>/', lab_views.doctor_lab_test_detail, name='doctor_lab_test_detail'),
    path('patient/lab-test/<int:pk>/', lab_views.patient_lab_test_detail, name='patient_lab_test_detail'),
    # Staff Calendar API
    path('api/appointments/calendar/', staff_views.staff_calendar_events, name='staff_calendar_events'),
    path('doctor-leaves/', clinic_admin_views.doctor_leaves, name='doctor_leaves'),
    path('doctor-leaves/<int:leave_id>/approve/', clinic_admin_views.approve_doctor_leave, name='approve_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/reject/', clinic_admin_views.reject_doctor_leave, name='reject_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/edit/', clinic_admin_views.edit_doctor_leave, name='edit_doctor_leave'),
    path('doctor-leaves/<int:leave_id>/cancel/', clinic_admin_views.cancel_doctor_leave, name='cancel_doctor_leave'),
    path('request-leave/', doctor_views.request_leave, name='request_leave'),
    path('api/labs/available/', lab_views.get_available_labs, name='get_available_labs'),
]

router = DefaultRouter()
router.register(r'lab-tests', LabTestViewSet, basename='lab-test')
router.register(r'labs', LabManagementViewSet, basename='lab-management')

urlpatterns += path('api/', include(router.urls)),

urlpatterns += [
    path('api/', include(router.urls)),
] 