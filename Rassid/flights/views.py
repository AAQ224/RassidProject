from django.shortcuts import render, get_object_or_404

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from .models import Flight, GateAssignment, FlightStatusHistory
from .serializers import (
    FlightSerializer,
    GateAssignmentSerializer,
    FlightStatusHistorySerializer,
)
from users.permissions import IsAirportAdmin, IsOperator


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



def flights_list(request):
    """
    Operator flights list page
    Template: flights/operator/flights_list.html
    """
    flights = Flight.objects.all().order_by("scheduledDeparture")
    return render(request, "flights/operator/flights_list.html", {
        "flights": flights,
    })


def edit_flight(request, pk):
    """
    Edit / view single flight
    Template: flights/operator/edit_flight.html
    """
    flight = get_object_or_404(Flight, pk=pk)
    return render(request, "flights/operator/edit_flight.html", {
        "flight": flight,
    })


def passenger_list(request, pk):
    """
    Passengers list for specific flight
    Template: flights/operator/passenger_list.html
    """
    flight = get_object_or_404(Flight, pk=pk)

    passengers = []

    return render(request, "flights/operator/passenger_list.html", {
        "flight": flight,
        "passengers": passengers,
    })
