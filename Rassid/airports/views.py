from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import stripe

from .models import Airport, AirportSubscription, SubscriptionRequest, Payment
from flights.services import flights_api
from .serializers import AirportSerializer, AirportSubscriptionSerializer, SubscriptionRequestSerializer
from .forms import AirportSignupForm
from users.permissions import IsSuperAdmin
from flights.models import Flight
from tickets.models import Ticket

User = get_user_model()

class AirportViewSet(viewsets.ModelViewSet):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

class AirportSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = AirportSubscription.objects.all()
    serializer_class = AirportSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

class SubscriptionRequestViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionRequest.objects.all()
    serializer_class = SubscriptionRequestSerializer


def request_subscription(request):
    if request.method == 'POST':
        form = AirportSignupForm(request.POST, request.FILES)
        if form.is_valid():
            subscription = form.save()
            
            subject = f"New Subscription: {subscription.airport_name}"
            
            context = {
                'airport_name': subscription.airport_name,
                'airport_code': subscription.airport_code,
                'city': subscription.city,
                'country': subscription.country,
                'plan': subscription.get_selected_plan_display(),
                'email': subscription.admin_email,
                'phone': subscription.admin_phone, 
                'admin_url': request.build_absolute_uri('/platform-admin/') 
            }

            html_message = render_to_string('emails/new_request.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL], 
                    html_message=html_message,
                    fail_silently=True
                )
            except:
                pass

            messages.success(request, "Your request has been submitted successfully!")
            return redirect('public_home')
    else:
        initial_plan = request.GET.get('plan', '1_year')
        form = AirportSignupForm(initial={'selected_plan': initial_plan})

    return render(request, 'airports/subscription_request.html', {'form': form})

@login_required
def dashboard(request):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')

    my_airport = get_object_or_404(Airport, id=request.user.airport_id)
    today = timezone.now().date()
    now = timezone.now()

    employees = User.objects.filter(role='operator', airport_id=request.user.airport_id)

    total_flights = Flight.objects.filter(origin=my_airport).count()
    today_flights = Flight.objects.filter(
        origin=my_airport, 
        scheduledDeparture__date=today
    ).count()

    tickets = Ticket.objects.filter(airport=my_airport).select_related('createdBy').order_by('-createdAt')
    total_tickets = tickets.count()

    upcoming_flights = Flight.objects.filter(
        origin=my_airport,
        scheduledDeparture__gte=now
    ).order_by('scheduledDeparture')[:5]

    try:
        from notifications.models import EmailLog
        email_logs = EmailLog.objects.filter(recipient=request.user.email)
        total_logs = email_logs.count()
        failed_logs = email_logs.filter(status='Failed').count()
        
        if total_logs > 0:
            success_rate = int(((total_logs - failed_logs) / total_logs) * 100)
        else:
            success_rate = 0 # Default if no logs
            
        notification_success_rate = f"{success_rate}%"
        notification_failed_count = failed_logs
    except ImportError:
        notification_success_rate = "0%"
        notification_failed_count = 0

    active_subscription = AirportSubscription.objects.filter(airport=my_airport, status='active').first()
    
    # Calculate usage percent
    employees_count = employees.count()
    if active_subscription and active_subscription.max_employees > 0:
        usage_percent = int((employees_count / active_subscription.max_employees) * 100)
    else:
        usage_percent = 0
    
    payment_history = SubscriptionRequest.objects.filter(
        admin_email=request.user.email,
        airport_code=my_airport.code
    ).order_by('-created_at')

    context = {
        'airport': my_airport,
        'total_flights': total_flights,
        'today_flights': today_flights,
        'total_tickets': total_tickets,
        'upcoming_flights': upcoming_flights,
        'employees': employees,
        'employees_count': employees_count,
        'usage_percent': usage_percent,
        'active_subscription': active_subscription, 
        'tickets': tickets,
        'payments': payment_history,
        'notification_success_rate': notification_success_rate,
        'notification_failed_count': notification_failed_count,
        'active_subscription': active_subscription,
    }
    
    return render(request, "airports/dashboard.html", context)

@login_required
def employees_list(request):
    if request.user.role != 'airport_admin':
        return redirect('public_home')
    employees = User.objects.filter(role='operator', airport_id=request.user.airport_id)
    return render(request, "airports/employees_list.html", {"employees": employees})

@login_required
def add_employee(request):
    if request.user.role != 'airport_admin':
        return redirect('public_home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        role = request.POST.get('role', 'operator')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, "airports/add_employee.html")

        try:
            User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                role=role,
                airport_id=request.user.airport_id
            )
            messages.success(request, "Employee added successfully.")
            return redirect('airport_admin_employees')
        except Exception as e:
            messages.error(request, f"Error creating user: {e}")

    return render(request, "airports/add_employee.html")

@login_required
def edit_employee(request, employee_id):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')

    employee = get_object_or_404(User, id=employee_id)

    if employee.airport_id != request.user.airport_id:
        messages.error(request, "You are not authorized to edit this employee.")
        return redirect('airport_admin_employees')

    if request.method == 'POST':
        employee.first_name = request.POST.get('first_name')
        employee.last_name = request.POST.get('last_name')
        employee.email = request.POST.get('email')
        employee.phone_number = request.POST.get('phone_number')
        employee.role = request.POST.get('role', 'operator')
        employee.is_active = request.POST.get('is_active') == 'on'
        
        employee.save()
        messages.success(request, "Employee updated successfully.")
        return redirect('airport_admin_employees')

    my_airport = get_object_or_404(Airport, id=request.user.airport_id)

    context = {
        'employee': employee,
        'airport': my_airport
    }
    return render(request, 'airports/edit_employee.html', context)

@login_required
def delete_employee(request, employee_id):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        messages.error(request, "Access denied.")
        return redirect('public_home')

    employee = get_object_or_404(User, id=employee_id)

    if employee.airport_id != request.user.airport_id:
        messages.error(request, "You cannot delete an employee from another airport.")
        return redirect('airport_admin_employees')

    if employee.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('airport_admin_employees')

    employee.delete()
    messages.success(request, "Employee deleted successfully.")
    
    return redirect('airport_admin_employees')

@login_required
def airport_settings(request):
    if request.user.role != 'airport_admin':
        return redirect('public_home')
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.save()
        
        messages.success(request, 'Profile updated successfully.')
        return redirect('airport_settings')

    airport_id = request.user.airport_id
    airport = None
    subscription = None
    if airport_id:
        airport = get_object_or_404(Airport, id=airport_id)
        subscription = AirportSubscription.objects.filter(airport=airport).first()
    
    return render(request, "airports/airport_settings.html", {
        "airport": airport,
        "subscription": subscription,
    })


@login_required
def approve_subscription(request, request_id):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied")
        return redirect('public_home')

    sub_request = get_object_or_404(SubscriptionRequest, id=request_id)

    if sub_request.status == 'approved':
        messages.warning(request, "This request is already approved.")
        return redirect('platform_admin_dashboard')

    try:
        generated_password = get_random_string(length=12)

        if User.objects.filter(email=sub_request.admin_email).exists():
             messages.error(request, "User with this email already exists.")
             return redirect('platform_admin_dashboard')

        new_admin = User.objects.create_user(
            email=sub_request.admin_email,
            password=generated_password,
            first_name=sub_request.admin_name,
            role='airport_admin',
            is_active=True
        )

        new_airport = Airport.objects.create(
            name=sub_request.airport_name,
            code=sub_request.airport_code,
            city=sub_request.city,
            country=sub_request.country
        )

        new_admin.airport_id = new_airport.id 
        new_admin.save()

        AirportSubscription.objects.create(
            airport=new_airport,
            plan=sub_request.selected_plan,
            is_active=True
        )

        sub_request.status = 'approved'
        sub_request.save()

        subject = "Welcome! Your Airport Platform Account is Ready"
        login_url = request.build_absolute_uri('/login/')
        
        context = {
            'admin_name': sub_request.admin_name,
            'airport_name': sub_request.airport_name,
            'email': sub_request.admin_email,
            'password': generated_password,
            'login_url': login_url
        }

        html_message = render_to_string('emails/subscription_approved.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [sub_request.admin_email],
            html_message=html_message,
            fail_silently=False
        )

        messages.success(request, f"Airport {new_airport.name} created and credentials sent to admin.")

    except Exception as e:
        messages.error(request, f"Error approving request: {str(e)}")

    return redirect('platform_admin_dashboard')

def payment_checkout(request, request_id):
    sub_req = get_object_or_404(SubscriptionRequest, id=request_id)
    
    if sub_req.status != 'approved_pending_payment':
        if sub_req.status == 'approved':
             return redirect('users:login')
        messages.warning(request, "Invalid request status.")
        return redirect('public_home')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': 49900, # $499.00
                    'product_data': {
                        'name': f'Activation Fee - {sub_req.airport_name}',
                        'description': f"Plan: {sub_req.get_selected_plan_display()}",
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.build_absolute_uri(reverse('airport_payment_success', args=[sub_req.id])) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('airport_payment_checkout', args=[sub_req.id])),
        )
        
        return render(request, 'airports/payment_checkout.html', {
            'request_obj': sub_req,
            'session_id': checkout_session.id,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY
        })

    except Exception as e:
        messages.error(request, f"Error connecting to payment gateway: {str(e)}")
        return redirect('public_home')

@transaction.atomic
def payment_success(request, request_id):
    sub_req = get_object_or_404(SubscriptionRequest, id=request_id)

    session_id = request.GET.get('session_id')

    if not session_id:
         messages.error(request, "No payment session detected.")
         return redirect('airport_payment_checkout', request_id=request_id)

    if sub_req.status != 'approved_pending_payment':
        if sub_req.status == 'approved':
             return redirect('users:login')
        messages.warning(request, "This request is not awaiting payment.")
        return redirect('public_home')
        
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status != 'paid':
             messages.error(request, "Payment not confirmed.")
             return redirect('airport_payment_checkout', request_id=request_id)

        if User.objects.filter(email=sub_req.admin_email).exists():
            messages.error(request, "User with this email already exists.")
            return redirect('public_home')

        airport = Airport.objects.filter(code=sub_req.airport_code).first()
        if not airport:
            airport = Airport.objects.create(
                name=sub_req.airport_name,
                code=sub_req.airport_code,
                city=sub_req.city,
                country=sub_req.country
            )

        password = get_random_string(length=12)
        user = User.objects.create_user(
            email=sub_req.admin_email,
            password=password,
            role='airport_admin',
            airport_id=airport.id
        )

        years = 1
        if sub_req.selected_plan == '3_years':
            years = 3
        elif sub_req.selected_plan == '5_years':
            years = 5
            
        start_date = timezone.now()
        end_date = start_date + timedelta(days=365*years)

        AirportSubscription.objects.create(
            airport=airport,
            plan_type=sub_req.get_selected_plan_display(),
            start_at=start_date,
            expire_at=end_date,
            status='active'
        )

        Payment.objects.create(
            airport=airport,
            amount=499.00,
            plan_name=sub_req.get_selected_plan_display(),
            status='Paid'
        )

        sub_req.status = 'approved'
        sub_req.save()

        subject = "Welcome to RASSID - Workspace Activated"
        login_url = request.build_absolute_uri('/login/')
        
        context = {
            'airport_name': airport.name,
            'email': sub_req.admin_email,
            'password': password,
            'login_url': login_url
        }

        html_message = render_to_string('emails/credentials_email.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [sub_req.admin_email],
            html_message=html_message,
            fail_silently=False
        )
        
        try:
             from notifications.models import EmailLog
             EmailLog.objects.create(
                recipient=sub_req.admin_email,
                subject="Account Credentials",
                status="Sent"
            )
        except:
            pass

        return render(request, 'users/login.html', {
            'messages': [f'Success! Account for {airport.name} is now active. Please check your email for credentials.']
        })

    except Exception as e:
        transaction.set_rollback(True)
        messages.error(request, f"Activation error: {str(e)}")
        return redirect('airport_payment_checkout', request_id=request_id)


@login_required
def sync_flights_data(request):
    if request.method != "POST":
         return redirect('airport_dashboard')
         
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        messages.error(request, "Permission denied.")
        return redirect('public_home')
        
    airport = get_object_or_404(Airport, id=request.user.airport_id)
    
    try:
        data = flights_api.fetch_flights(airport_code=airport.code)
        flights_api.save_flights_to_db(data)
        messages.success(request, f"Successfully synced flights for {airport.code}.")
    except Exception as e:
        messages.error(request, f"Error syncing flights: {str(e)}")
        
    return redirect('airport_dashboard')

@login_required
def renew_subscription(request):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')

    if request.method == 'POST':
        plan = request.POST.get('plan', '1_year')
        airport = get_object_or_404(Airport, id=request.user.airport_id)
        
        last_req = SubscriptionRequest.objects.filter(admin_email=request.user.email).last()
        
        new_req = SubscriptionRequest.objects.create(
            airport_name=airport.name,
            airport_code=airport.code,
            country=airport.country,
            city=airport.city,
            admin_email=request.user.email,
            admin_phone=request.user.phone_number or "0000000000",
            selected_plan=plan,
            status='approved_pending_payment',
            official_license=last_req.official_license if last_req else None 
        )
        
        return redirect('airport_payment_checkout', request_id=new_req.id)

    return render(request, 'airports/renew_subscription.html')

@login_required
def flight_reports(request):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')
        
    airport = get_object_or_404(Airport, id=request.user.airport_id)
    
    from flights.models import FlightStatusHistory, GateAssignment, Flight
    from django.db.models import Count, Avg, F, DurationField, ExpressionWrapper
    
    my_flights = Flight.objects.filter(origin=airport)
    total_updates = FlightStatusHistory.objects.filter(flight__in=my_flights).count()
    
    gate_assignments = GateAssignment.objects.filter(flight__in=my_flights, releasedAt__isnull=False)
    if gate_assignments.exists():
        avg_duration = gate_assignments.annotate(
            duration=ExpressionWrapper(F('releasedAt') - F('assignedAt'), output_field=DurationField())
        ).aggregate(Avg('duration'))['duration__avg']
        
        if avg_duration:
            total_seconds = int(avg_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            avg_gate_time = f"{hours}h {minutes}m"
        else:
            avg_gate_time = "0h 0m"
    else:
        avg_gate_time = "N/A"

    try:
        from notifications.models import EmailLog
        email_logs = EmailLog.objects.filter(recipient=request.user.email)
        total_logs = email_logs.count()
        failed_logs = email_logs.filter(status='Failed').count()
        if total_logs > 0:
            success_rate = int(((total_logs - failed_logs) / total_logs) * 100)
        else:
            success_rate = 0
    except:
        success_rate = 0
        
    most_changed_flights = my_flights.annotate(
        changes_count=Count('flightstatushistory')
    ).order_by('-changes_count')[:5]

    context = {
        'airport': airport,
        'total_updates': total_updates,
        'avg_gate_time': avg_gate_time,
        'notification_success_rate': success_rate,
        'most_changed_flights': most_changed_flights
    }
    
    return render(request, 'airports/flight_reports.html', context)

@login_required
def notification_insights(request):
    if request.user.role != 'airport_admin' or not request.user.airport_id:
        return redirect('public_home')
        
    try:
        from notifications.models import EmailLog
        from django.utils import timezone
        
        logs = EmailLog.objects.filter(recipient=request.user.email).order_by('-sent_at')[:50]
        
        today = timezone.now().date()
        dates = []
        delivery_rates = []
        failed_counts = []
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            day_logs = EmailLog.objects.filter(
                recipient=request.user.email, 
                sent_at__date=date
            )
            total = day_logs.count()
            failed = day_logs.filter(status='Failed').count()
            sent = total - failed
            
            rate = int((sent / total) * 100) if total > 0 else 0
            
            dates.append(date.strftime("%b %d"))
            delivery_rates.append(rate)
            failed_counts.append(failed)
            
    except ImportError:
        logs = []
        dates = []
        delivery_rates = []
        failed_counts = []

    context = {
        'logs': logs,
        'dates': dates,
        'delivery_rates': delivery_rates,
        'failed_counts': failed_counts
    }
    return render(request, 'airports/notification_insights.html', context)

@login_required
def cancel_subscription_request(request, request_id):
    if request.user.role != 'airport_admin':
        return redirect('public_home')
        
    sub_request = get_object_or_404(SubscriptionRequest, id=request_id, admin_email=request.user.email)
    
    if sub_request.status in ['pending', 'approved_pending_payment']:
        sub_request.status = 'rejected' # Mark as rejected/cancelled
        sub_request.save()
        messages.success(request, "Request cancelled successfully.")
    else:
        messages.error(request, "Cannot cancel this request active or already processed.")
        
    return redirect('airport_dashboard')