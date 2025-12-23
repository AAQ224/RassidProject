from django.shortcuts import render, get_object_or_404, redirect
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from .models import Passenger, PassengerFlight
from .serializers import PassengerSerializer, PassengerFlightSerializer
from users.permissions import IsAirportAdmin, IsOperator
from django.utils import timezone
from flights.models import FlightStatusHistory, GateAssignment

class PassengerViewSet(ModelViewSet):
    queryset = Passenger.objects.all()
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsOperator]

class PassengerFlightViewSet(ModelViewSet):
    queryset = PassengerFlight.objects.all()
    serializer_class = PassengerFlightSerializer
    permission_classes = [IsAuthenticated, IsOperator]

def tracking(request):
    return render(request, "passengers/tracking.html")

def passenger_tracker(request, token):
    """
    Public tracking page for passengers. 
    Accessible via secure token.
    """
    passenger = get_object_or_404(Passenger, trackingToken=token)
    
    p_flight = PassengerFlight.objects.filter(passenger=passenger).select_related('flight', 'flight__origin', 'flight__destination').order_by('-flight__scheduledDeparture').first()
    
    if not p_flight:
        return render(request, "passengers/tracker.html", {
            "passenger": passenger,
            "flight": None,
            "error": "No upcoming flights found."
        })

    flight = p_flight.flight
    
    timeline = []
    
    status_history = FlightStatusHistory.objects.filter(flight=flight).order_by('changedAt')
    for h in status_history:
        timeline.append({
            'type': 'status',
            'timestamp': h.changedAt,
            'title': f"Status Changed to {h.newStatus}",
            'description': f"Flight status updated from {h.oldStatus} to {h.newStatus}"
        })
        
    gate_history = GateAssignment.objects.filter(flight=flight).order_by('assignedAt')
    for g in gate_history:
        timeline.append({
            'type': 'gate',
            'timestamp': g.assignedAt,
            'title': f"Gate Assigned: {g.gateCode}",
            'description': f"Terminal {g.terminal}. Boarding: {g.boardingOpenTime.strftime('%H:%M')}"
        })
        
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)
    
    current_gate = gate_history.last()
    
    total_seconds_open = 0
    total_seconds_close = 0
    phase = "unknown"
    
    if current_gate and current_gate.boardingOpenTime and current_gate.boardingCloseTime:
        now = timezone.now()
        open_time = current_gate.boardingOpenTime
        close_time = current_gate.boardingCloseTime
        
        if now < open_time:
            phase = "pre_open"
            total_seconds_open = int((open_time - now).total_seconds())
        elif now < close_time:
            phase = "boarding"
            total_seconds_close = int((close_time - now).total_seconds())
        else:
            phase = "closed"

    def format_time(seconds):
        if seconds < 0: return "00:00:00"
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}"

    return render(request, "passengers/tracker.html", {
        "passenger": passenger,
        "flight": flight,
        "timeline": timeline,
        "gate": current_gate,
        "now": timezone.now(),
        "phase": phase,
        "seconds_to_open": total_seconds_open,
        "seconds_to_close": total_seconds_close,
        "formatted_open": format_time(total_seconds_open),
        "formatted_close": format_time(total_seconds_close)
    })
