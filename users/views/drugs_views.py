from django.http import JsonResponse
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from ..models import Drug
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

def drug_suggestions(request):
    try:
        query = request.GET.get('query', '').strip()
        if not query:
            return JsonResponse([])  # Return empty array if no query

        # Query the drugs and remove duplicates using values() and distinct()
        suggestions = Drug.objects.filter( 
            Q(product_name__icontains=query) |
            Q(salt_composition__icontains=query)
        ).values('product_name', 'salt_composition', 'product_manufactured').distinct()[:10]
        
        # Format the response to match the template expectations
        data = [
            {
                'product_name': drug['product_name'],
                'salt_composition': drug['salt_composition'],
                'product_manufactured': drug['product_manufactured']
            } 
            for drug in suggestions
        ]
        
        return JsonResponse(data, safe=False)  # Return array directly
        
    except Exception as e:
        print(f"Error in drug suggestions: {str(e)}")
        return JsonResponse([], safe=False)  # Return empty array on error

@api_view(['GET'])
#@permission_classes([IsAuthenticated])
def api_drug_suggestions(request):
    try:
        query = request.GET.get('query', '').strip()
        if not query:
            return Response([])

        suggestions = Drug.objects.filter(
            Q(product_name__icontains=query) |
            Q(salt_composition__icontains=query)
        ).values('product_name', 'salt_composition', 'product_manufactured').distinct()[:10]
        
        data = [
            {
                'product_name': drug['product_name'],
                'salt_composition': drug['salt_composition'],
                'product_manufactured': drug['product_manufactured']
            } 
            for drug in suggestions
        ]
        
        return Response(data)
        
    except Exception as e:
        print(f"Error in drug suggestions API: {str(e)}")
        return Response([], status=500)