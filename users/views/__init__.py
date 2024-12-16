from .auth_views import (
    login_api,
    signup_api,
    get_user_profile,
    verify_doctor_api,
)

from .patient_views import (
    create_patient,
    patients_list,
    
    
)

from .appointment_views import (
    create_appointment,
    AppointmentView,
    AppointmentListView,
    AppointmentCreateView,
    appointments_view,
    appointment_detail,
    appointment_delete,
)

from .template_views import (
    login_view,
    signup_view,
    dashboard_view,
    appointments_view,
    appointments_list,
    appointment_detail,
    appointment_delete,
    profile_view,
    profile_edit_view,
    logout_view,
    patients_view,
    patient_detail,
    patient_edit,
    
)

from .utils import (
    get_tokens_for_user,
    log_error,
    get_csrf_token,
)

from .doctor_views import (
    verify_doctor_api_view,
    save_doctor,
    get_doctors_list,
    dashboard_view,
    doctor_dashboard,
)

__all__ = [
    # Auth views
    'login_api',
    'signup_api',
    'get_user_profile',
    'verify_doctor_api',
    
    # Patient views
    'create_patient',
    'get_patients',
    'patients_view',
    'patient_detail',
    'patient_edit',
    'patient_form',
    
    # Appointment views
    'create_appointment',
    'AppointmentView',
    'AppointmentListView',
    'AppointmentCreateView',
    
    # Template views
    'login_view',
    'signup_view',
    'Dashboard',
    'dashboard_view',
    'appointments_list',
    'appointment_detail',
    'appointment_delete',
    'profile_view',
    'profile_edit_view',
    'logout_view',
    
    # Utils
    'get_tokens_for_user',
    'log_error',
    'get_csrf_token',
    
    # Doctor views
    'verify_doctor',
    'save_doctor',
    'get_doctors_list',
    'dashboard_view',
] 