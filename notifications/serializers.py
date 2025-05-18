from rest_framework import serializers
from .models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True, default='System')
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    related_object_type_str = serializers.SerializerMethodField()

    def get_related_object_type_str(self, obj):
        if obj.content_type:
            return obj.content_type.model
        return None

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
            'is_read', 
            'timestamp',
            'content_type',
            'object_id',
            'related_object_type_str',
            'action_url'
        ]
        read_only_fields = [
            'id', 
            'recipient', 
            'recipient_username', 
            'sender', 
            'sender_username', 
            'timestamp',
            'content_type',
            'object_id',
            'related_object_type_str',
            'action_url'
        ] 