from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from .models import Flight, GateAssignment, FlightStatusHistory
from .serializers import (
    FlightSerializer,
    GateAssignmentSerializer,
    FlightStatusHistorySerializer,
)
from users.permissions import IsAirportAdmin, IsOperator
from airports.models import Airport
from django.utils import timezone


class FlightViewSet(ModelViewSet):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    permission_classes = [IsAuthenticated, IsAirportAdmin]


class GateAssignmentViewSet(ModelViewSet):
    queryset = GateAssignment.objects.all()
    serializer_class = GateAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAirportAdmin]


class FlightStatusHistoryViewSet(ModelViewSet):
    queryset = FlightStatusHistory.objects.all()
    serializer_class = FlightStatusHistorySerializer
    permission_classes = [IsAuthenticated, IsOperator]


@login_required
def flights_list(request):
    """
    Operator flights list page
    Template: flights/operator/flights_list.html
    """
    if request.user.role != 'operator' or not request.user.airport_id:
        return render(request, "flights/operator/flights_list.html", {"flights": []})

    today = timezone.now().date()
    
    # Existing Flight Filter Logic
    flights = Flight.objects.filter(origin_id=request.user.airport_id, status__iexact='scheduled').order_by("scheduledDeparture")
    
    # Get distinct destinations for the dropdown
    destinations = Airport.objects.filter(
        id__in=flights.values_list('destination_id', flat=True).distinct()
    ).order_by('city')

    # Apply filters
    search_query = request.GET.get('search')
    if search_query:
        flights = flights.filter(flightNumber__icontains=search_query)

    destination_id = request.GET.get('destination')
    if destination_id:
        flights = flights.filter(destination_id=destination_id)

    date_filter = request.GET.get('date')
    if date_filter:
        flights = flights.filter(scheduledDeparture__date=date_filter)

    # --- Ticketing Embed ---
    from tickets.models import Ticket
    from tickets.forms import TicketForm
    
    my_tickets = Ticket.objects.filter(createdBy=request.user).order_by('-createdAt')
    ticket_form = TicketForm()

    return render(request, "flights/operator/flights_list.html", {
        "flights": flights,
        "search_query": search_query,
        "destinations": destinations,
        "selected_destination": int(destination_id) if destination_id else None,
        "selected_date": date_filter,
        "my_tickets": my_tickets,
        "ticket_form": ticket_form,
    })


@login_required
def edit_flight(request, pk):
    """
    Edit / view single flight
    Template: flights/operator/edit_flight.html
    """
    flight = get_object_or_404(Flight, pk=pk)

    # Security check: Ensure operator owns this flight (origin airport)
    if request.user.role != 'operator' or not request.user.airport_id:
         return redirect('public_home')
    
    if flight.origin_id != request.user.airport_id:
         messages.error(request, "You do not have permission to edit this flight.")
         return redirect('operator_flights_list')

    # Get existing gate assignment if any
    gate_assignment = GateAssignment.objects.filter(flight=flight).first()

    if request.method == 'POST':
        # Update Flight Details
        flight.status = request.POST.get('status')
        # Handle dates only if provided
        dep_time = request.POST.get('scheduledDeparture')
        if dep_time:
            flight.scheduledDeparture = dep_time
        
        flight.save()

        # Update Gate Assignment
        gate_code = request.POST.get('gateCode')
        terminal = request.POST.get('terminal')
        boarding_open = request.POST.get('boardingOpenTime')
        boarding_close = request.POST.get('boardingCloseTime')

        if gate_code and terminal:
            if not gate_assignment:
                gate_assignment = GateAssignment(flight=flight)
            
            gate_assignment.gateCode = gate_code
            gate_assignment.terminal = terminal
            if boarding_open:
                gate_assignment.boardingOpenTime = boarding_open
            if boarding_close:
                gate_assignment.boardingCloseTime = boarding_close
            
            gate_assignment.save()

        messages.success(request, "Flight details updated successfully.")
        return redirect('operator_flights_list')

    return render(request, "flights/operator/edit_flight.html", {
        "flight": flight,
        "gate_assignment": gate_assignment
    })


@login_required
def passenger_list(request, pk):
    """
    Passengers list for specific flight
    Template: flights/operator/passenger_list.html
    """
    flight = get_object_or_404(Flight, pk=pk)
    
    # Security check
    if request.user.role != 'operator' or flight.origin_id != request.user.airport_id:
         return redirect('operator_flights_list')

    try:
        from passengers.models import PassengerFlight
        passenger_flights = PassengerFlight.objects.filter(flight=flight).select_related('passenger')
    except ImportError:
        passenger_flights = []

    return render(request, "flights/operator/passenger_list.html", {
        "flight": flight,
        "passenger_flights": passenger_flights,
    })

@login_required
def fetch_flights(request):
    """
    Manually trigger flight data fetch
    """
    if request.user.role != 'operator' or not request.user.airport_id:
         messages.error(request, "Permission denied")
         return redirect('public_home')
         
    try:
        from .tasks import update_flights_task
        from airports.models import Airport
        
        # Get operator's airport code
        airport = Airport.objects.get(id=request.user.airport_id)
        
        # Run synchronous update for the specific airport
        update_flights_task(airport_code=airport.code) 
        
        messages.success(request, f"Flight data fetched successfully for {airport.code}.")
    except Airport.DoesNotExist:
         messages.error(request, "Operator airport not found.")
    except Exception as e:
        messages.error(request, f"Error fetching data: {str(e)}")
        
    return redirect('operator_flights_list')
