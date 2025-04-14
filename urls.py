from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import login_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('labs/', include('labs.urls', namespace='labs')),
    path('users/', include('RxBackend.users.urls')),
    path('login/', login_view, name='login'),
    #path('', include(('users.urls', 'users'), namespace='users')),  # This will catch all other URLs
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)