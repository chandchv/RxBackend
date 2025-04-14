from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        null=True,  # Allow system notifications without a specific sender
        blank=True
    )
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=50, blank=True, null=True) # e.g., 'appointment', 'message', 'lab_result'

    # Optional: Link to a related object (e.g., the specific appointment or lab order)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-timestamp'] # Show newest first
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"To: {self.recipient.username} - Read: {self.is_read} - {self.message[:30]}"

    # Optional: Method to easily get the URL for the related object
    def get_related_object_url(self):
        if self.related_object:
            try:
                # Assumes your related models have a 'get_absolute_url' method
                return self.related_object.get_absolute_url()
            except AttributeError:
                # Handle cases where the related object doesn't have a URL
                # Or implement custom logic based on notification_type/content_type
                pass
        return None
