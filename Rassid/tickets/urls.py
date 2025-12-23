from django.urls import path
from . import views

urlpatterns = [
    # Operator URLs
    path('create/', views.create_ticket, name='create_ticket'),
    path('my-tickets/', views.operator_tickets_list, name='operator_tickets_list'),

    # Admin URLs
    path('manage/', views.admin_tickets_list, name='admin_tickets_list'),
    path('manage/<int:pk>/', views.admin_ticket_detail, name='admin_ticket_detail'),
]
