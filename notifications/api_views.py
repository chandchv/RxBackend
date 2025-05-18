from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from .models import Notification
from .serializers import NotificationSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_notification_count(request):
    """
    API endpoint to get the count of unread notifications for the logged-in user.
    """
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'unread_count': count}, status=status.HTTP_200_OK)

class NotificationListView(generics.ListAPIView):
    """
    API endpoint to list notifications for the logged-in user.
    Supports filtering by 'read' status and pagination.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).order_by('-timestamp')
        read_status = self.request.query_params.get('read')
        if read_status is not None:
            read_bool = read_status.lower() in ['true', '1']
            queryset = queryset.filter(is_read=read_bool)
        return queryset

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_as_read(request, notification_id):
    """
    API endpoint to mark a specific notification as read.
    """
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save()
        serializer = NotificationSerializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_as_read(request):
    """
    API endpoint to mark all unread notifications for the logged-in user as read.
    """
    updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({'message': f'{updated_count} notifications marked as read.'}, status=status.HTTP_200_OK) 