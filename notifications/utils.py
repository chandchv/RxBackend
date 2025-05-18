from django.contrib.contenttypes.models import ContentType
from .models import Notification
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def create_notification(recipient=None, message=None, notification_type=None, sender=None, action_url=None, related_object=None):
    """
    Create a new notification with standardized parameters
    
    Args:
        recipient: The user who will receive the notification (required)
        message: The notification message (required)
        notification_type: Type of notification (e.g., 'prescription_new', 'appointment_new')
        sender: The user who triggered the notification (optional)
        action_url: URL to redirect when notification is clicked (optional)
        related_object: The related object for this notification (optional)
    
    Returns:
        Notification object if created successfully, None otherwise
    """
    try:
        if not recipient:
            logger.error("No recipient provided for notification")
            raise ValueError("Recipient is required for notification")

        if not message:
            logger.error("No message provided for notification")
            raise ValueError("Message is required for notification")

        # Handle related object if provided
        content_type = None
        object_id = None
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            object_id = related_object.id
            logger.debug(f"Created notification with related object: {content_type.model} #{object_id}")

        # Create the notification
        notification = Notification.objects.create(
            recipient=recipient,
            message=message,
            notification_type=notification_type,
            sender=sender,
            action_url=action_url,
            content_type=content_type,
            object_id=object_id
        )
        
        logger.info(f"Created notification #{notification.id} for user {recipient.username} of type {notification_type}")
        return notification
        
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}", exc_info=True)
        return None
