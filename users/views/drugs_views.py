from django.http import JsonResponse
from ..models import Drug

def drug_suggestions(request):
    query = request.GET.get('query', '')
    suggestions = Drug.search_suggestions(query)
    return JsonResponse(list(suggestions), safe=False)