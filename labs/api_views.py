from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsLabOwnerOrStaff
from .serializers import LabResultUploadSerializer
import hashlib

class LabResultUploadView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsLabOwnerOrStaff]
    
    def post(self, request, *args, **kwargs):
        serializer = LabResultUploadSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                result = serializer.save()
                
                # Calculate file hash
                result_file = result.result_file
                sha256_hash = hashlib.sha256()
                for chunk in result_file.chunks():
                    sha256_hash.update(chunk)
                result.file_hash = sha256_hash.hexdigest()
                result.save()
                
                return Response({
                    'status': 'success',
                    'message': 'Result uploaded successfully',
                    'result_id': result.id
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 