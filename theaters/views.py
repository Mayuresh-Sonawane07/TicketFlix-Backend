from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from .models import Theater, Screen, Show, Seat
from .serializers import TheaterSerializer, ScreenSerializer, ShowSerializer, SeatSerializer


class TheaterViewSet(viewsets.ModelViewSet):
    queryset = Theater.objects.all()
    serializer_class = TheaterSerializer

    def get_queryset(self):
        return Theater.objects.all()

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        return {'request': self.request}

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_venues(self, request):
        theaters = Theater.objects.filter(manager=request.user)
        serializer = self.get_serializer(theaters, many=True)
        return Response(serializer.data)


class ScreenViewSet(viewsets.ModelViewSet):
    queryset = Screen.objects.all() 
    serializer_class = ScreenSerializer

    def get_queryset(self):
        return Screen.objects.all()
        theater_id = self.request.query_params.get('theater')
        if theater_id:
            queryset = queryset.filter(theater_id=theater_id)
        return queryset

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        print("CREATE SCREEN DATA:", request.data)
        response = super().create(request, *args, **kwargs)
        screen_id = response.data['id']
        screen = Screen.objects.get(id=screen_id)
        self._generate_seats(screen)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        screen = self.get_object()
        # Regenerate seats if counts changed
        Seat.objects.filter(screen=screen).delete()
        self._generate_seats(screen)
        return response

    def _generate_seats(self, screen):
        seats = []
        for category, count, prefix in [
            ('Silver', screen.silver_count, 'S'),
            ('Gold', screen.gold_count, 'G'),
            ('Platinum', screen.platinum_count, 'P'),
        ]:
            for i in range(1, count + 1):
                seats.append(Seat(
                    screen=screen,
                    seat_number=f"{prefix}{i}",
                    category=category,
                ))
        Seat.objects.bulk_create(seats)


class ShowViewSet(viewsets.ModelViewSet):
    queryset = Show.objects.all() 
    serializer_class = ShowSerializer

    def get_queryset(self):
        from django.utils import timezone
        queryset = Show.objects.filter(show_time__gte=timezone.now())
        event_id = self.request.query_params.get('event')
        city = self.request.query_params.get('city')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        if city:
            queryset = queryset.filter(screen__theater__city__iexact=city)
        return queryset

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'])
    def available_seats(self, request, pk=None):
        from bookings.views import release_expired_pending_bookings
        release_expired_pending_bookings()  # ← add this
        show = self.get_object()
        all_seats = Seat.objects.filter(screen=show.screen)
        booked_seat_ids = set(Seat.objects.filter(
            booking__show=show,
            booking__status__in=['Booked', 'Pending']
        ).values_list('id', flat=True))

        result = []
        for seat in all_seats:
            result.append({
                'id': seat.id,
                'seat_number': seat.seat_number,
                'category': seat.category,
                'is_booked': seat.id in booked_seat_ids,
            })
        return Response(result)


class SeatViewSet(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer