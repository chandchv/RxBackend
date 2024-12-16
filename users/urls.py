from django.urls import path, include
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
    auth_views,
    api_views,
    
)
from .views.template_views import (
    signup_view,
    login_view,
    dashboard_view,
    appointments_view,
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
)
from .views.patient_views import (
    create_patient,
    patients_list,
    patient_detail,
    patient_edit,
)
from .views.prescription_views import (
    create_prescription,
    prescription_detail,
    patient_prescriptions,
    prescriptions_view,
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
)

from .views import auth_views

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
    
    # Doctor URLs
    path('doctor/dashboard/', doctor_views.doctor_dashboard, name='doctor_dashboard'),
    path('doctors/', DoctorListView.as_view(), name='doctors_list'),
    path('doctors/create/', DoctorCreateView.as_view(), name='create_doctor'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/save/', save_doctor, name='save_doctor'),
    path('doctors/verify/', verify_doctor_api_view, name='verify_doctor'),
    path('doctors/appointments/', doctor_views.doctor_appointments, name='doctor_appointments'),
    path('doctors/appointments/create/', doctor_views.create_appointment, name='create_appointment'),
    path('doctors/appointments/<int:appointment_id>/', doctor_views.appointment_detail, name='appointment_detail'),
    
    # Authentication & Profile URLs
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    
    # Dashboard
    path('dashboard/', dashboard_view, name='dashboard'),
    path('patients/', patients_view, name='patients_list'),
    path('patients/create/', create_patient, name='create_patient'),
    path('appointments/', appointments_view, name='appointments'),
    
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
        path('login/', login_view, name='login'),
        path('logout/', logout_view, name='logout'),
        path('signup/', signup_view, name='signup'),
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
    path('doctor/appointments/', doctor_views.doctor_appointments, name='doctor_appointments'),
    path('doctor/appointments/create/', doctor_views.create_appointment, name='create_appointment'),
    
    # Patient URLs
    path('doctor/patients/', patient_views.patients_list, name='patients_list'),
    path('doctor/patients/create/', patient_views.create_patient, name='create_patient'),
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),
    path('doctor/patients/<int:patient_id>/edit/', patient_views.patient_edit, name='patient_edit'),
    #path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    
    # Prescription URLs
    path('doctor/patients/<int:patient_id>/prescriptions/create/', 
         prescription_views.create_prescription, name='create_prescription'),
    path('doctor/prescriptions/<int:pk>/', 
         prescription_views.prescription_detail, name='prescription_detail'),
    path('doctor/patients/<int:patient_id>/prescriptions/', 
         prescription_views.patient_prescriptions, name='patient_prescriptions'),
    path('doctor/dashboard/', doctor_views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/patients/<int:patient_id>/', patient_views.patient_detail, name='patient_detail'),

    # Authentication URLs
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # API URLs
    path('api/appointments/', api_views.appointment_list, name='api_appointments'),
    path('api/appointments/<int:appointment_id>/status/', 
         api_views.update_appointment_status, name='api_update_appointment_status'),
    
    # Default dashboard
    path('dashboard/', doctor_views.doctor_dashboard, name='dashboard'),
    
]