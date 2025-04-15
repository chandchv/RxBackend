from django.urls import path, include
from .api_views import (
    get_unread_notification_count,
    NotificationListView as APINotificationListView,
    mark_notification_as_read,
    mark_all_notifications_as_read
)
from .views import NotificationListView

app_name = 'notifications'

# Web view URLs
urlpatterns = [
    path('list/', NotificationListView.as_view(), name='list'),
    
    # API endpoints
    path('api/', include([
        path('', APINotificationListView.as_view(), name='api-list'),
        path('count/', get_unread_notification_count, name='count'),
        path('<int:notification_id>/read/', mark_notification_as_read, name='mark-read'),
        path('read-all/', mark_all_notifications_as_read, name='mark-all-read'),
    ])),
] 