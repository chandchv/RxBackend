from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import login_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),  # Remove the 'users/' prefix if it's causing conflicts
    path('login/', login_view, name='login'),
    path('', include(('users.urls', 'users'), namespace='users')),  # Make sure this line exists
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)