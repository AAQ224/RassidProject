from airports.models import SubscriptionRequest

def pending_requests_count(request):
    if request.user.is_authenticated and request.user.is_superuser:
        count = SubscriptionRequest.objects.filter(status='pending').count()
        return {'pending_requests_count': count}
    return {}
