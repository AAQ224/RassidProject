from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, TicketCommentViewSet
from . import views

router = DefaultRouter()
router.register("tickets", TicketViewSet)
router.register("comments", TicketCommentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("tickets/", views.tickets_list, name="tickets_list"),
    path("tickets/<int:pk>/", views.ticket_details, name="ticket_details"),
]
