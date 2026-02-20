from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Booking
from .serializers import BookingSerializer
from theaters.models import Seat
from django.db import transaction

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def create(self, request, *args, **kwargs):
        seat_ids = request.data.get('seats', [])
        show_id = request.data.get('show')
        
        with transaction.atomic():
            existing_bookings = Booking.objects.filter(show_id=show_id, status='Booked', seats__in=seat_ids)
            if existing_bookings.exists():
                return Response({'error': 'One or more selected seats are already booked.'}, status=status.HTTP_400_BAD_REQUEST)
            
            return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.is_cancellable():
            booking.status = 'Cancelled'
            booking.save()
            return Response({'status': 'Booking cancelled successfully.'})
        else:
            return Response({'error': 'Booking cannot be cancelled. Less than 24 hours to showtime or already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
