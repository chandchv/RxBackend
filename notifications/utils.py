from django.contrib.contenttypes.models import ContentType
from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

def create_notification(recipient, message, sender=None, notification_type=None, related_object=None, action_url=None):
    """Helper function to create a notification."""
    if recipient is None:
        print(f"Warning: Recipient is None. Notification not created.")
        return None
        
    if not isinstance(recipient, User):
        print(f"Warning: Invalid recipient type: {type(recipient)}") # Basic check
        return None

    content_type = None
    object_id = None
    if related_object:
        content_type = ContentType.objects.get_for_model(related_object)
        object_id = related_object.pk

    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        message=message,
        notification_type=notification_type,
        content_type=content_type,
        object_id=object_id,
        action_url=action_url
    )
    # Optional: Trigger real-time update via WebSockets here if using them
    return notification
