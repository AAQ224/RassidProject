from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FlightViewSet, GateAssignmentViewSet, FlightStatusHistoryViewSet
from . import views

router = DefaultRouter()
router.register("flights", FlightViewSet)
router.register("gate-assignments", GateAssignmentViewSet)
router.register("status-history", FlightStatusHistoryViewSet)

urlpatterns = [
    path("flights/", views.flights_list, name="operator_flights_list"),
    path("dashboard/", views.flights_list, name="operator_dashboard"),
    path("flights/<int:pk>/edit/", views.edit_flight, name="operator_edit_flight"),
    path("flights/fetch/", views.fetch_flights, name="operator_fetch_flights"),
    path("flights/<int:pk>/passengers/", views.passenger_list, name="operator_passenger_list"),
    path("", include(router.urls)),
]
