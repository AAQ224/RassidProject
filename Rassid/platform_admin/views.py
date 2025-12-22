from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
import random
import string
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse

from airports.models import Airport, AirportSubscription, SubscriptionRequest
from flights.models import Flight
from tickets.models import Ticket
from passengers.models import PassengerFlight
from notifications.models import EmailLog

User = get_user_model()

def is_super_admin(user):
    return user.is_authenticated and user.is_superuser

def redirect_back(request, fallback='platform_dashboard', anchor=''):
    referer = request.META.get('HTTP_REFERER', fallback)
    if anchor:
        if '#' in referer:
            referer = referer.split('#')[0]
        return redirect(f"{referer}#{anchor}")
    return redirect(referer)

@login_required
def admin_dashboard(request):
    if not is_super_admin(request.user):
        return redirect('public_home')

    emails_sent_count = EmailLog.objects.filter(status='Sent').count()
    emails_failed_count = EmailLog.objects.filter(status='Failed').count()

    today = timezone.now().date()
    passengers_today = PassengerFlight.objects.filter(
        flight__scheduledDeparture__date=today
    ).count()

    total_ops = emails_sent_count + emails_failed_count
    if total_ops > 0 and emails_failed_count > 0:
        uptime_calc = ((total_ops - emails_failed_count) / total_ops) * 100
        system_uptime = f"{uptime_calc:.1f}%"
    else:
        system_uptime = "100%"

    stats = {
        "airports_count": Airport.objects.count(),
        "active_subscriptions": AirportSubscription.objects.filter(status='active').count(),
        "employees_count": User.objects.filter(role='airport_staff').count(),
        "passengers_today": passengers_today,
        "emails_delivered": emails_sent_count,
        "api_errors": emails_failed_count,
        "system_uptime": system_uptime
    }

    latest_airports_qs = Airport.objects.all().order_by('-id')[:5]
    latest_airports = []
    for airport in latest_airports_qs:
        sub = AirportSubscription.objects.filter(airport=airport).first()
        airport.status = sub.status if sub else 'Inactive'
        latest_airports.append(airport)
    
    admins = User.objects.filter(role='airport_admin')[:5]
    

    recent_tickets = Ticket.objects.select_related('airport').all().order_by('-createdAt')[:5]
 

    context = {
        "stats": stats,
        "latest_airports": latest_airports,
        "admins": admins,
        "tickets": recent_tickets
    }
    return render(request, "platform_admin/dashboard.html", context)

@login_required
def subscription_requests_list(request):
    if not is_super_admin(request.user):
        return redirect('public_home')
    
    requests = SubscriptionRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'platform_admin/requests_list.html', {'requests': requests})

@login_required
def request_details(request, request_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    
    sub_req = get_object_or_404(SubscriptionRequest, id=request_id)
    return render(request, 'platform_admin/request_details.html', {'req': sub_req})

@login_required
@transaction.atomic
def approve_request(request, request_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
        
    sub_req = get_object_or_404(SubscriptionRequest, id=request_id)
    
    # Allow approval if pending OR if already in payment pending (e.g. resending email)
    if sub_req.status not in ['pending', 'approved_pending_payment']:
        messages.warning(request, "This request has already been processed or is fully active.")
        return redirect('admin_requests_list')

    try:
        # Check email availability early
        if User.objects.filter(email=sub_req.admin_email).exists():
            messages.error(request, f"Review Failed: A user with email {sub_req.admin_email} already exists.")
            return redirect('admin_requests_list')

        # Update status to waiting for payment
        sub_req.status = 'approved_pending_payment'
        sub_req.reviewed_by = request.user
        sub_req.save()

        # Build Checkout URL (Public URL)
        # Assuming we add this URL path to airports/urls.py
        checkout_url = request.build_absolute_uri(reverse('airport_payment_checkout', args=[sub_req.id]))

        # Send Payment Request Email
        subject = "Application Approved - Activation Payment Required"
        context = {
            'airport_name': sub_req.airport_name,
            'checkout_url': checkout_url
        }
        
        html_message = render_to_string('emails/payment_request.html', context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [sub_req.admin_email],
                html_message=html_message,
                fail_silently=False
            )
            
            EmailLog.objects.create(
                recipient=sub_req.admin_email,
                subject="Payment Request",
                status="Sent"
            )
            messages.success(request, f"Application for {sub_req.airport_name} approved! Payment request email sent to applicant.")
            
        except Exception as email_error:
            EmailLog.objects.create(
                recipient=sub_req.admin_email,
                subject="Payment Request",
                status="Failed",
                error_message=str(email_error)
            )
            messages.warning(request, f"Approved, but failed to send email: {email_error}")
        
    except Exception as e:
        transaction.set_rollback(True)
        messages.error(request, f"System Error: {str(e)}")
        
    return redirect('admin_requests_list')

@login_required
def reject_request(request, request_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    sub_req = get_object_or_404(SubscriptionRequest, id=request_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        to_email = request.POST.get('email', sub_req.admin_email).strip() or sub_req.admin_email

        sub_req.status = 'rejected'
        sub_req.reviewed_by = request.user
        sub_req.save()

        subject = "Update on your RASSID Subscription Request"
        message = f"Dear Applicant,\n\nUnfortunately, we could not approve your request for {sub_req.airport_name}.\n\n"
        if reason:
            message += f"Reason provided by admin:\n{reason}\n\n"
        message += "Please contact support for more details.\n\nRegards,\nRASSID Team"

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [to_email],
                fail_silently=False
            )
            EmailLog.objects.create(
                recipient=to_email,
                subject="Request Rejected",
                status="Sent"
            )
            messages.success(request, "Request rejected and email sent to applicant.")
        except Exception as e:
            EmailLog.objects.create(
                recipient=to_email,
                subject="Request Rejected",
                status="Failed",
                error_message=str(e)
            )
            messages.warning(request, f"Request rejected but email failed to send: {e}")

        return redirect('admin_requests_list')

    # If not POST, redirect back to details page
    return redirect('admin_request_details', request_id)

@login_required
def airports(request):
    if not is_super_admin(request.user):
        return redirect('public_home')
    airports_qs = Airport.objects.all().order_by("code")
    return render(request, "platform_admin/airports.html", {
        "airports": airports_qs,
    })

@login_required
def subscriptions(request):
    if not is_super_admin(request.user):
        return redirect('public_home')
    subs = AirportSubscription.objects.select_related("airport").all()
    return render(request, "platform_admin/subscriptions.html", {
        "subscriptions": subs,
    })

@login_required
def system_errors(request):
    if not is_super_admin(request.user):
        return redirect('public_home')
    errors = []
    return render(request, "platform_admin/system_errors.html", {
        "errors": errors,
    })

@login_required
def airport_details(request, id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    airport = get_object_or_404(Airport, id=id)
    subscription = AirportSubscription.objects.filter(airport=airport).first()
    admin_user = User.objects.filter(airport_id=airport.id, role='airport_admin').first()
    
    context = {
        'airport': airport,
        'subscription': subscription,
        'admin_user': admin_user,
    }
    return render(request, 'platform_admin/airport_details.html', context)

@login_required
def renew_subscription(request, id):
    if not is_super_admin(request.user):
        return redirect('public_home')
        
    subscription = get_object_or_404(AirportSubscription, airport_id=id)
    
    if subscription.expire_at:
        subscription.expire_at = subscription.expire_at + timedelta(days=365)
    else:
        subscription.expire_at = datetime.now() + timedelta(days=365)
        
    subscription.status = 'active'
    subscription.save()
    
    messages.success(request, f"Subscription renewed for {subscription.airport.name} successfully!")
    return redirect_back(request, anchor='subscription-section')

@login_required
def toggle_subscription_status(request, id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    
    airport = get_object_or_404(Airport, id=id)
    subscription = AirportSubscription.objects.filter(airport=airport).first()
    
    if subscription:
        if subscription.status == 'active':
            subscription.status = 'suspended'
            messages.warning(request, f"Subscription suspended for {airport.name}.")
        else:
            subscription.status = 'active'
            messages.success(request, f"Subscription activated for {airport.name}.")
        subscription.save()
    else:
        messages.error(request, "No subscription found for this airport.")
    
    return redirect_back(request, anchor='subscription-section')

@login_required
def admin_reset_password(request, user_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    
    target_user = get_object_or_404(User, id=user_id)
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    target_user.set_password(new_password)
    target_user.save()
    
    messages.success(request, f"Password reset for {target_user.email}. New Password: {new_password}")
    return redirect_back(request, anchor='admin-section')

@login_required
def admin_toggle_user_access(request, user_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
    
    target_user = get_object_or_404(User, id=user_id)
    if target_user.is_active:
        target_user.is_active = False
        messages.warning(request, f"User {target_user.email} has been disabled.")
    else:
        target_user.is_active = True
        messages.success(request, f"User {target_user.email} has been enabled.")
    
    target_user.save()
    return redirect_back(request, anchor='admin-section')

@login_required
def delete_user(request, user_id):
    if not is_super_admin(request.user):
        return redirect('public_home')
        
    target_user = get_object_or_404(User, id=user_id)
    email = target_user.email
    
    if target_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect_back(request, anchor='admin-section')

    target_user.delete()
    messages.success(request, f"User {email} has been permanently deleted.")
    
    return redirect_back(request, anchor='admin-section')

@login_required
def admin_close_ticket(request, ticket_id):
    if not is_super_admin(request.user):
        return redirect('public_home')

    try:
        ticket = Ticket.objects.get(id=ticket_id)
        ticket.status = 'closed'
        ticket.save()
        messages.success(request, f"Ticket #{ticket_id} has been closed.")
    except Ticket.DoesNotExist:
        messages.error(request, "Ticket not found.")

    return redirect_back(request)