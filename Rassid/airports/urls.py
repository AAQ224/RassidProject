from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AirportViewSet, AirportSubscriptionViewSet, SubscriptionRequestViewSet, 
    dashboard, employees_list, add_employee, airport_settings, 
    request_subscription, approve_subscription, edit_employee, delete_employee,
    request_subscription, approve_subscription, edit_employee, delete_employee,
    payment_checkout, payment_success, sync_flights_data, renew_subscription,
    flight_reports, notification_insights, cancel_subscription_request
)

router = DefaultRouter()
router.register("list", AirportViewSet)
router.register("subscriptions", AirportSubscriptionViewSet)
router.register("requests", SubscriptionRequestViewSet)

urlpatterns = [
    path("api/", include(router.urls)),

    path('register/', request_subscription, name='request_subscription'),

    path('admin/approve/<int:request_id>/', approve_subscription, name='approve_subscription'),

    path('payment/checkout/<int:request_id>/', payment_checkout, name='airport_payment_checkout'),
    path('payment/success/<int:request_id>/', payment_success, name='airport_payment_success'),
    
    path('subscription/cancel/<int:request_id>/', cancel_subscription_request, name='cancel_subscription_request'),

    path("dashboard/", dashboard, name="airport_dashboard"),
    path("dashboard/sync-flights/", sync_flights_data, name="sync_flights_data"),
    
    path("employees/", employees_list, name="airport_admin_employees"),
    path("employees/add/", add_employee, name="airport_admin_add_employee"),
    path("employees/edit/<int:employee_id>/",edit_employee, name="airport_admin_edit_employee"),
    path("employees/delete/<int:employee_id>/", delete_employee, name="airport_admin_delete_employee"),
    path("subscription/renew/", renew_subscription, name="airport_renew_subscription"),
    path("reports/flights/", flight_reports, name="airport_flight_reports"),
    path("reports/notifications/", notification_insights, name="airport_notification_insights"),
    path("settings/", airport_settings, name="airport_settings"), 
]