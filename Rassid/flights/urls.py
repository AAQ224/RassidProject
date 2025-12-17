from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FlightViewSet, GateAssignmentViewSet, FlightStatusHistoryViewSet
from . import views

router = DefaultRouter()
router.register("flights", FlightViewSet)
router.register("gate-assignments", GateAssignmentViewSet)
router.register("status-history", FlightStatusHistoryViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("flights/", views.flights_list, name="operator_flights_list"),
    path("flights/<int:pk>/edit/", views.edit_flight, name="operator_edit_flight"),
    path("flights/<int:pk>/passengers/", views.passenger_list, name="operator_passenger_list"),
]
