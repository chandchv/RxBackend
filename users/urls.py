from django.urls import path

from .views import signup_view, login_view, get_user_profile, verify_doctor, create_patient, get_patients, PatientsView, AppointmentView

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('profile/', get_user_profile, name='user-profile'),
    path('verify-doctor/', verify_doctor, name='verify-doctor'),
    path('patients/', create_patient, name='create-patient'),
    path('patients/all/', get_patients, name='get-patients'),
    path('api/users/patients/', PatientsView.as_view(), name='patients'),
    path('api/users/appointments/', AppointmentView.as_view(), name='appointments'),
]
    # ... other paths ...
