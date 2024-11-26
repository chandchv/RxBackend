from django.urls import path
from .views import signup_view, login_view, get_user_profile

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('profile/', get_user_profile, name='user-profile'),
]
    # ... other paths ...
