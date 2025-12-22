from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, EmailLogViewSet

router = DefaultRouter()
router.register(r'list', NotificationViewSet)
router.register(r'email-logs', EmailLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]