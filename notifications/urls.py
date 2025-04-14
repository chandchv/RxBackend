from django.urls import path
from .api_views import (
    get_unread_notification_count,
    NotificationListView,
    mark_notification_as_read,
    mark_all_notifications_as_read
)

app_name = 'notifications_api'

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('count/', get_unread_notification_count, name='notification-count'),
    path('<int:notification_id>/read/', mark_notification_as_read, name='notification-mark-read'),
    path('read-all/', mark_all_notifications_as_read, name='notification-mark-all-read'),
] 