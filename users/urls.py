from django.urls import path

from .views import signup_view, login_view, get_user_profile, verify_doctor

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('profile/', get_user_profile, name='user-profile'),
    path('verify-doctor/', verify_doctor, name='verify-doctor'),
]
    # ... other paths ...
