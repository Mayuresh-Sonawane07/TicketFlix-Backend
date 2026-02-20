from rest_framework import viewsets
from .models import Theater, Screen, Show, Seat
from .serializers import TheaterSerializer, ScreenSerializer, ShowSerializer, SeatSerializer
from rest_framework.decorators import action
from rest_framework.response import Response

class TheaterViewSet(viewsets.ModelViewSet):
    queryset = Theater.objects.all()
    serializer_class = TheaterSerializer

class ScreenViewSet(viewsets.ModelViewSet):
    queryset = Screen.objects.all()
    serializer_class = ScreenSerializer

class ShowViewSet(viewsets.ModelViewSet):
    queryset = Show.objects.all()
    serializer_class = ShowSerializer

    def get_queryset(self):
        queryset = Show.objects.all()
        movie_id = self.request.query_params.get('movie', None)
        city = self.request.query_params.get('city', None)
        if movie_id is not None:
            queryset = queryset.filter(movie_id=movie_id)
        if city is not None:
            queryset = queryset.filter(screen__theater__city__iexact=city)
        return queryset

    @action(detail=True, methods=['get'])
    def available_seats(self, request, pk=None):
        show = self.get_object()
        all_seats = Seat.objects.filter(screen=show.screen)
        booked_seats = Seat.objects.filter(booking__show=show, booking__status='Booked')
        available_seats = all_seats.exclude(id__in=booked_seats.values_list('id', flat=True))
        serializer = SeatSerializer(available_seats, many=True)
        return Response(serializer.data)

class SeatViewSet(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
