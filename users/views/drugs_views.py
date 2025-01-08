from django.http import JsonResponse
from django.db.models import Q
from ..models import Drug

def drug_suggestions(request):
    try:
        query = request.GET.get('query', '').strip()
        if not query:
            return JsonResponse([])  # Return empty array if no query

        # Query the drugs
        suggestions = Drug.objects.filter(
            Q(product_name__icontains=query) |
            Q(salt_composition__icontains=query)
        )[:10]  # Limit to 10 suggestions
        
        # Format the response to match the template expectations
        data = [
            {
                'product_name': drug.product_name,
                'salt_composition': drug.salt_composition
            } 
            for drug in suggestions
        ]
        
        return JsonResponse(data, safe=False)  # Return array directly
        
    except Exception as e:
        print(f"Error in drug suggestions: {str(e)}")
        return JsonResponse([], safe=False)  # Return empty array on error