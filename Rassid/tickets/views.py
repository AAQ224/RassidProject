from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Ticket, TicketComment
from .forms import TicketForm, CommentForm
from airports.models import Airport

@login_required
def create_ticket(request):
    """Operator creates a ticket"""
    if request.user.role != 'operator' or not request.user.airport_id:
        messages.error(request, "Access denied.")
        return redirect('public_home')

    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.createdBy = request.user
            ticket.airport_id = request.user.airport_id
            ticket.save()
            messages.success(request, "Ticket created successfully.")
            return redirect('operator_flights_list')
    else:
        form = TicketForm()

    return render(request, 'tickets/operator/create_ticket.html', {'form': form})

@login_required
def operator_tickets_list(request):
    """List of tickets created by the operator"""
    if request.user.role != 'operator':
         return redirect('public_home')
         
    tickets = Ticket.objects.filter(createdBy=request.user).order_by('-createdAt')
    return render(request, 'tickets/operator/ticket_list.html', {'tickets': tickets})

@login_required
def admin_tickets_list(request):
    """List of tickets for the airport admin"""
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')

    # Show tickets for this admin's airport
    tickets = Ticket.objects.filter(airport_id=request.user.airport_id).order_by('-createdAt')
    return render(request, 'tickets/admin/ticket_list.html', {'tickets': tickets})

@login_required
def admin_ticket_detail(request, pk):
    """Admin view to manage a ticket"""
    if request.user.role != 'airport_admin':
        return redirect('public_home')

    ticket = get_object_or_404(Ticket, pk=pk, airport_id=request.user.airport_id)
    comments = TicketComment.objects.filter(ticket=ticket).order_by('commentedAt')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'escalate':
            ticket.status = 'Escalated'
            ticket.save()
            messages.success(request, "Ticket escalated to Platform Admin.")
        
        elif action == 'reject':
            ticket.status = 'Rejected'
            ticket.save()
            messages.info(request, "Ticket rejected/closed.")
            
        elif action == 'comment':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.ticket = ticket
                comment.user = request.user
                comment.save()
                messages.success(request, "Note added.")
        
        return redirect('admin_ticket_detail', pk=pk)

    else:
        comment_form = CommentForm()

    return render(request, 'tickets/admin/ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'comment_form': comment_form
    })
