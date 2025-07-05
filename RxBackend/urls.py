"""
URL configuration for RxBackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.conf.urls.i18n import i18n_patterns 
from users.views.dashboard_views import dashboard_redirect

# Redirect root to the dashboard view for proper role-based routing
def redirect_to_home(request):
    return redirect('home')

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'detail': 'CSRF cookie set'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_redirect, name='home'),
    path('users/', include('users.urls', namespace='users')),
    path('labs/', include('labs.urls', namespace='labs')),
    path('pharmacy/', include('pharmacy.urls', namespace='pharmacy')),
    path('billing/', include('billing.urls', namespace='billing')),
    # path('health/', include('HealthRecords.urls', namespace='health')),  # Commented out as module not found
    path('appointments/', include('appointment.urls', namespace='appointment')),
    path('accounts/', include('allauth.urls')),
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path("api/token-auth/", obtain_auth_token, name="api_token_auth"),
    path('api/notifications/', include('notifications.urls')),  # No namespace needed - it's in the app
    path('api/get-csrf-token/', get_csrf_token),
    path('i18n/', include('django.conf.urls.i18n')),
    path('scheduling/', include('scheduling.urls', namespace='scheduling')),
]

# Add static and media URL patterns
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
