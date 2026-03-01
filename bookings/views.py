from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Booking
from .serializers import BookingSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "Admin":
            return Booking.objects.all()
        return Booking.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        if request.user.role != "Customer":
            return Response(
                {"error": "Only customers can book tickets."},
                status=status.HTTP_403_FORBIDDEN
            )
        seat_ids = request.data.get('seats', [])
        show_id = request.data.get('show')
        if not seat_ids or not show_id:
            return Response(
                {"error": "Show and seats are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            existing = Booking.objects.filter(
                show_id=show_id,
                status='Booked',
                seats__in=seat_ids
            )
            if existing.exists():
                return Response(
                    {'error': 'One or more seats are already booked.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Create booking with Pending status
            request.data['status'] = 'Pending'
            request.data['user'] = request.user.id
            return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """Called after UPI payment redirect"""
        booking = self.get_object()
        if booking.user != request.user:
            return Response(
                {"error": "Unauthorized."},
                status=status.HTTP_403_FORBIDDEN
            )
        if booking.status == 'Booked':
            return Response({"message": "Already confirmed."})

        booking.status = 'Booked'
        booking.transaction_id = request.data.get('transaction_id', f"UPI-{booking.id}")
        booking.save()
        return Response({
            "message": "Payment confirmed! Booking successful.",
            "booking": BookingSerializer(booking).data
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.user != request.user:
            return Response(
                {"error": "You can only cancel your own booking."},
                status=status.HTTP_403_FORBIDDEN
            )
        if booking.is_cancellable():
            booking.status = 'Cancelled'
            booking.save()
            return Response({'status': 'Booking cancelled successfully.'})
        return Response(
            {'error': 'Cannot cancel. Less than 24 hours to showtime or already cancelled.'},
            status=status.HTTP_400_BAD_REQUEST
        )