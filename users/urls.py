from django.urls import path, include

from .views import doctor_views, staff_views, admin_views
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
)

from .views.drugs_views import (
    drug_suggestions,
)

from .views.template_views import (
    signup_view,
    login_view,
    dashboard_view,
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
)

from .views.auth_views import (
    
    login_api,
    logout_api,
    signup_api,
    doctor_signup_api,
    patient_signup_api,
    doctor_signup_view,
    patient_signup_view,
    
    
)

from .views.api_views import (
    get_patient_appointments,
    get_doctors,
    get_clinic_appointments,
    get_clinic_doctors,
    get_clinic_staff,
)

from .views import dashboard_views
from .views import appointment_views
from .views import clinic_admin_views

app_name = 'users'

# API URLs
api_urlpatterns = [
    
    path('appointments/', AppointmentView.as_view(), name='appointments_api'),
    path('appointments/list/', AppointmentListView.as_view(), name='appointments_list_api'),
    path('appointments/create/', AppointmentCreateView.as_view(), name='appointment_create_api'),
]

# Main URLs
urlpatterns = [
    # Patient URLs
    path('patients/create/', create_patient, name='create_patient'),
    path('patients/', patients_list, name='patients_list'),
    path('patients/list/', patients_list, name='get_patients'),
    path('patients/<int:patient_id>/', patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/edit/', patient_edit, name='patient_edit'),
    path('patients/form/', patient_form, name='patient_form'),
    path('patient_detail/<int:patient_id>/', patient_detail, name='patient_detail'),
    
    # Appointment URLs
    path('appointments/', appointments_view, name='appointments'),
    path('appointments/create/', create_appointment, name='create_appointment'),
    path('appointment/<int:pk>/', AppointmentView.as_view(), name='appointment_detail'),
    path('appointment/<int:pk>/delete/', appointment_delete, name='appointment_delete'),
    
   
    
    # Authentication & Profile URLs
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'), 
    
    # Dashboard
   
    path('doctor/dashboard/', dashboard_views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    path('doctor/admin/dashboard/', dashboard_views.admin_dashboard, name='admin_dashboard'),
    path('clinic/admin/dashboard/', dashboard_views.admin_dashboard, name='clinic_admin_dashboard'),
    path('dashboard/', dashboard_views.dashboard_redirect, name='dashboard'),

    #Prescription URLs
    #path('prescriptions/', get_prescriptions, name='prescriptions'),
    path('prescriptions/create/', create_prescription, name='create_prescription'),
    path('prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    #path('prescriptions/<int:pk>/edit/', prescription_edit, name='prescription_edit'),
    path('prescriptions/list/', prescriptions_view, name='prescriptions_list'),
    path('prescriptions/patient/<int:patient_id>/', patient_prescriptions, name='patient_prescriptions'),
    #path('prescriptions/print/<int:pk>/', prescription_print, name='prescription_print'),

    # API URLs
     path('api/', include(([
        path('doctors/', DoctorListView.as_view(), name='get_doctors_list'),
        path('patients/', patients_list, name='get_patients'),
        path('appointments/', AppointmentListView.as_view(), name='get_appointments_list'),
        #path('prescriptions/', get_prescriptions, name='get_prescriptions_list'),
       # path('clinics/', get_clinics_list, name='get_clinics_list'),
        #path('staff/', get_staff_list, name='get_staff_list'),
       # path('users/', get_users_list, name='get_users_list'),
        path('login/', login_api, name='login'),
        path('logout/', logout_api, name='logout'),
        path('signup/', signup_api, name='signup'),
        path('doctor/signup/', doctor_signup_api, name='doctor_signup'),
        path('patient/signup/', patient_signup_api, name='patient_signup'),
        path('get-csrf-token/', api_views.get_csrf_token, name='get_csrf_token'),
        path('appointments/', get_patient_appointments, name='get_patient_appointments'),
        path('doctors/', get_doctors, name='get_doctors'),
        path('clinic/appointments/', get_clinic_appointments, name='get_clinic_appointments'),
        path('clinic/doctors/', get_clinic_doctors, name='get_clinic_doctors'),
        path('clinic/staff/', get_clinic_staff, name='get_clinic_staff'),
        path('patient/appointments/', api_views.patient_appointments, name='patient_appointments'),
        path('patient/prescriptions/', api_views.patient_prescriptions, name='api_patient_prescriptions'),
        path('patient/prescriptions_detail/<int:pk>/', api_views.patient_prescriptions_detail, name='patient_prescriptions_detail'),

        #path('doctors/', get_doctors, name='get_doctors'),
        
    ], 'api'))),

   
    # Clinic Admin URLs - Updated paths
    path('clinic-admin/', clinic_admin_dashboard, name='clinic_admin_dashboard'),
    path('clinic-admin/profile/', clinic_profile, name='clinic_profile'),
    
    # Doctor management
    path('clinic-admin/doctors/', doctors_list, name='doctors_list'),
    path('clinic-admin/doctors/add/', add_doctor, name='add_doctor'),
    path('clinic-admin/doctors/verify/', verify_doctor_credentials, name='verify_doctor_credentials'),
    path('clinic-admin/doctors/<int:doctor_id>/edit/', edit_doctor, name='edit_doctor'),
    path('clinic-admin/doctors/<int:doctor_id>/delete/', delete_doctor, name='delete_doctor'),
    
    # Staff management
    path('clinic-admin/staff/', staff_list, name='staff_list'),
    path('clinic-admin/staff/add/', add_staff, name='add_staff'),
    path('clinic-admin/staff/<int:staff_id>/edit/', edit_staff, name='edit_staff'),
    path('clinic-admin/staff/<int:staff_id>/toggle-status/', toggle_staff_status, name='toggle_staff_status'),

    # Doctor URLs
    path('doctor/appointments/', doctor_views.doctor_appointments_view, name='doctor_appointments_view'),
    path('doctor/appointments/create/', doctor_views.create_appointment, name='doctor_create_appointment'),
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
    path('doctors/appointments/<int:appointment_id>/', doctor_views.appointment_detail, name='appointment_detail'),

    
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
    path('api/doctor/appointments/', api_views.doctor_appointments, name='doctor_appointments'),
    
    # Patient API endpoints
    path('api/patient/appointments/', api_views.patient_appointments, name='patient_appointments'),
    
    # Clinic Profile endpoints
    path('api/clinic/profile/', api_views.clinic_profile_api, name='clinic_profile_api'),
    
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
    path('doctor/leaves/', doctor_views.manage_leaves, name='manage_leaves'),
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
    path('appointments/<int:appointment_id>/update-status/', 
         appointment_views.update_appointment_status, 
         name='update_appointment_status'),
    path('appointments/<int:appointment_id>/', appointment_views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:appointment_id>/delete/', appointment_views.appointment_delete, name='appointment_delete'),
    path('appointments/<int:appointment_id>/edit/', appointment_views.appointment_edit, name='appointment_edit'),
    path('doctor/<int:doctor_id>/details/', 
         clinic_admin_views.doctor_details, 
         name='doctor_details'),
]