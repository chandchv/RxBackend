from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    """
    Model to store user notifications.
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=50, blank=True, null=True)
    
    # For linking to any object (like a prescription, appointment, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Action URL for direct navigation from notification
    action_url = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Notification to {self.recipient}: {self.message[:50]}{'...' if len(self.message) > 50 else ''}"

    # Optional: Method to easily get the URL for the related object
    def get_related_object_url(self):
        if self.content_object:
            try:
                # Assumes your related models have a 'get_absolute_url' method
                return self.content_object.get_absolute_url()
            except AttributeError:
                # Handle cases where the related object doesn't have a URL
                # Or implement custom logic based on notification_type/content_type
                pass
        return None
