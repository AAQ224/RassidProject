from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == "superadmin"

class IsAirportAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == "airport_admin"

class IsOperator(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == "operator"
