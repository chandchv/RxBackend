from rest_framework import serializers
from .models import LabOrder, LabResult

class LabResultUploadSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(write_only=True)
    result_file = serializers.FileField()
    lab_metadata = serializers.JSONField(required=False)

    def validate_order_id(self, value):
        try:
            order = LabOrder.objects.get(id=value)
            if order.status not in ['PENDING_LAB', 'PROCESSING']:
                raise serializers.ValidationError("This order is not in a state that allows result upload.")
            return value
        except LabOrder.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

    def create(self, validated_data):
        order = LabOrder.objects.get(id=validated_data['order_id'])
        lab = self.context['request'].user.lab_profile
        
        # Create or update LabResult
        result, created = LabResult.objects.update_or_create(
            order=order,
            defaults={
                'result_file': validated_data['result_file'],
                'lab_metadata': validated_data.get('lab_metadata'),
                'uploaded_by_lab': lab
            }
        )
        
        # Update order status
        order.status = 'RESULT_UPLOADED'
        order.save()
        
        return result 