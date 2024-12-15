from rest_framework_simplejwt.tokens import RefreshToken
import logging
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def log_error(error, context=None):
    """Centralized error logging"""
    if context:
        logger.error(f"{context}: {str(error)}")
    else:
        logger.error(str(error))

@csrf_exempt
def get_csrf_token(request):
    """Get CSRF token for frontend"""
    return JsonResponse({'csrfToken': get_token(request)}) 