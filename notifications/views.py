from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Notification
from django.views.decorators.csrf import ensure_csrf_cookie

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

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})

@login_required
@require_http_methods(["POST"])
@ensure_csrf_cookie
def mark_all_notifications_read(request):
    """Mark all unread notifications as read for the current user."""
    try:
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse({
            'status': 'success',
            'message': f'{updated_count} notifications marked as read',
            'updated_count': updated_count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def get_unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})
