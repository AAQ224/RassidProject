from django.shortcuts import render, get_object_or_404
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .models import Ticket, TicketComment
from .serializers import TicketSerializer, TicketCommentSerializer
from users.permissions import IsAirportAdmin, IsOperator, IsSuperAdmin


class TicketViewSet(ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated, IsAirportAdmin | IsSuperAdmin]

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        ticket = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "status is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket.status = new_status
        ticket.save()
        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TicketCommentViewSet(ModelViewSet):
    queryset = TicketComment.objects.all()
    serializer_class = TicketCommentSerializer
    permission_classes = [IsAuthenticated, IsOperator | IsAirportAdmin | IsSuperAdmin]


def tickets_list(request):
    """
    Tickets list page
    Template: tickets/tickets_list.html
    """
    tickets = Ticket.objects.all()
    return render(request, "tickets/tickets_list.html", {
        "tickets": tickets,
    })


def ticket_details(request, pk):
    """
    Single ticket details page
    Template: tickets/ticket_details.html
    """
    ticket = get_object_or_404(Ticket, pk=pk)
    comments = TicketComment.objects.filter(ticket=ticket)

    return render(request, "tickets/ticket_details.html", {
        "ticket": ticket,
        "comments": comments,
    })
