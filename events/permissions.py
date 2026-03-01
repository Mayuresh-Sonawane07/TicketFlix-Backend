from rest_framework.permissions import BasePermission


class IsVenueOwner(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == "VENUE_OWNER"
        )