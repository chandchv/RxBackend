from django.urls import path, include
from .api_views import (
    get_unread_notification_count,
    NotificationListView as APINotificationListView,
    mark_notification_as_read,
    mark_all_notifications_as_read
)
from .views import NotificationListView
from . import views

app_name = 'notifications'

urlpatterns = [
    # Web views
    path('list/', NotificationListView.as_view(), name='list'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('unread-count/', views.get_unread_count, name='unread_count'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    
    # API endpoints
    path('api/', include([
        path('', APINotificationListView.as_view(), name='api-list'),
        path('count/', get_unread_notification_count, name='api-count'),
        path('<int:notification_id>/read/', mark_notification_as_read, name='api-mark-read'),
        path('read-all/', mark_all_notifications_as_read, name='api-mark-all-read'),
    ])),
] 