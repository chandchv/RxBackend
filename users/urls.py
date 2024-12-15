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
    get_patients,
    patient_detail,
    patient_edit,
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
)
from .views.patient_views import (
    create_patient,
    patients_list,
    get_patients,
)
from .views.prescription_views import (
    create_prescription,
    get_prescriptions,
    prescriptions_view,
    prescription_detail,
    prescription_edit,
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
    path('patients/list/', get_patients, name='get_patients'),
    path('patients/<int:pk>/', patient_detail, name='patient_detail'),
    path('patients/<int:pk>/edit/', patient_edit, name='patient_edit'),
    path('patients/form/', patient_form, name='patient_form'),
    
    # Appointment URLs
    path('appointments/', AppointmentListView.as_view(), name='appointments'),
    path('appointments/create/', AppointmentCreateView.as_view(), name='create_appointment'),
    path('appointment/<int:pk>/', AppointmentView.as_view(), name='appointment_detail'),
    
    
    # Doctor URLs
    path('doctors/', DoctorListView.as_view(), name='doctors_list'),
    path('doctors/create/', DoctorCreateView.as_view(), name='create_doctor'),
    path('doctors/<int:pk>/', DoctorDetailView.as_view(), name='doctor_detail'),
    path('doctors/save/', save_doctor, name='save_doctor'),
    path('doctors/verify/', verify_doctor_api_view, name='verify_doctor'),
    
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
    path('prescriptions/', get_prescriptions, name='prescriptions'),
    path('prescriptions/create/', create_prescription, name='create_prescription'),
    path('prescriptions/<int:pk>/', prescription_detail, name='prescription_detail'),
    path('prescriptions/<int:pk>/edit/', prescription_edit, name='prescription_edit'),
    path('prescriptions/list/', prescriptions_view, name='prescriptions_list'),
    
    # API URLs
     path('api/', include(([
        path('doctors/', DoctorListView.as_view(), name='get_doctors_list'),
        path('patients/', get_patients, name='get_patients'),
        path('appointments/', AppointmentListView.as_view(), name='get_appointments_list'),
        path('prescriptions/', get_prescriptions, name='get_prescriptions_list'),
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
]