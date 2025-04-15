from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Notification

# Create your views here.

class NotificationListView(LoginRequiredMixin, ListView):
    """View to display all notifications for a user"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
    def get_queryset(self):
        """Return only notifications for the current user"""
        return Notification.objects.filter(recipient=self.request.user).order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mark notifications as read when viewed
        if self.request.GET.get('mark_read', False):
            self.get_queryset().filter(is_read=False).update(is_read=True)
        return context
