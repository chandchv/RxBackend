from rest_framework import serializers
from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True, default='System')
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 
            'recipient', 
            'recipient_username',
            'sender', 
            'sender_username', 
            'message', 
            'notification_type', 
            'read', 
            'timestamp',
            'related_object_id',
            'related_object_type_str' # Use the string representation
        ]
        read_only_fields = [
            'id', 
            'recipient', 
            'recipient_username', 
            'sender', 
            'sender_username', 
            'timestamp',
            'related_object_type_str' # Make this read-only as well
        ] 