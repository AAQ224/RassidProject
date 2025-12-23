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
    airports = Airport.objects.all()
    return render(request, "public/airports_list.html", {"airports": airports})

def flights_list(request):
    from users.models import User
    from django.db.models import Q

    # Get IDs of airports that have an admin (managed airports)
    managed_airport_ids = User.objects.filter(role='airport_admin').values_list('airport_id', flat=True).distinct()
    
    flights = Flight.objects.filter(origin_id__in=managed_airport_ids, status__iexact='scheduled').select_related('origin', 'destination').prefetch_related('gateassignment_set').order_by("scheduledDeparture")

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