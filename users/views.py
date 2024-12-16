# This file is kept for backward compatibility
# All views have been moved to the views/ directory

from .views.auth_views import (
    login_api,
    signup_api,
    get_user_profile,
)

from .views.doctor_views import (
    DoctorCreateView,
    DoctorListView,
)

from .views.patient_views import (
    create_patient,
    get_patients,
    PatientsView,
    patient_detail,
    patient_edit,
)

from .views.appointment_views import (
    AppointmentView,
    AppointmentListView,
    AppointmentCreateView,
)

from .views.template_views import (
    signup_view,
    login_view,
    Dashboard,
    appointments_list,
    profile_view,
    logout_view,
)

from .views.utils import (
    get_tokens_for_user,
    log_error,
)



# Make dashboard directly available at the module level
Dashboard = Dashboard.as_view()

# Keep all exports explicit for better code tracking
__all__ = [
    # Auth views
    'login_api',
    'signup_api',
    'get_user_profile',
    
    # Patient views
    'create_patient',
    'get_patients',
    'PatientsView',
    
    # Appointment views
    'AppointmentView',
    'AppointmentListView',
    'AppointmentCreateView',
    
    # Template views
    'signup_view',
    'login_view',
    'dashboard_view',
    'appointments_view',
    'profile_view',
    'logout_view',
    
    # Utils
    'get_tokens_for_user',
    'log_error',

    # Doctor views
    'DoctorCreateView',
    'DoctorListView',
    'doctor_dashboard',
    'patient_detail',
    'patient_edit',
]
