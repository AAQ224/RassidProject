from django.shortcuts import render
from airports.models import Airport
from flights.models import Flight

def home(request):
    return render(request, "public/home.html", {
        "flights": Flight.objects.all()[:20]
    })

def about(request):
    return render(request, "public/about.html")

def airports_list(request):
    from airports.models import AirportSubscription
    from django.utils import timezone
    # Only airports with an active subscription (partner)
    active_subs = AirportSubscription.objects.filter(status='active', expire_at__gt=timezone.now())
    airports = Airport.objects.filter(id__in=active_subs.values_list('airport_id', flat=True))
    return render(request, "public/airports_list.html", {"airports": airports})

def flights_list(request):
    from users.models import User
    from django.db.models import Q

    # Get IDs of airports that have an admin (managed airports)
    managed_airport_ids = User.objects.filter(role='airport_admin').values_list('airport_id', flat=True).distinct()
    
    from django.utils import timezone
    from django.db.models import Q
    
    cutoff_time = timezone.now() - timezone.timedelta(hours=1)
    
    # Logic:
    # 1. Always show 'active' flights (flying now).
    # 2. Show 'scheduled'/'delayed'/etc if they are in the future or departed recently (<1h ago).
    # 3. Exclude 'landed' and 'cancelled' from the generic catch-all, but if 'active' is somehow flagged landed (unlikely), strict active takes precedence or we can exclude landed globally.
    # actually, simplest is: (Active) OR (Future/Recent AND NOT Landed AND NOT Cancelled)
    
    flights = Flight.objects.filter(
        origin_id__in=managed_airport_ids
    ).filter(
        Q(status__iexact='active') |
        (
            Q(scheduledDeparture__gte=cutoff_time) & 
            ~Q(status__iexact='landed') & 
            ~Q(status__iexact='cancelled')
        )
    ).select_related('origin', 'destination').prefetch_related('gateassignment_set').order_by("scheduledDeparture")

    # Search filter
    search_query = request.GET.get('search')
    if search_query:
        flights = flights.filter(
            Q(flightNumber__icontains=search_query) |
            Q(destination__city__icontains=search_query) |
            Q(destination__code__icontains=search_query)
        )

    return render(request, "public/flights_list.html", {
        "flights": flights,
        "search_query": search_query
    })

def pricing_view(request):
    return render(request, 'public/pricing.html')