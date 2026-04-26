from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Event, Review
from .serializers import EventSerializer, ReviewSerializer
from .permissions import IsVenueOwner

class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    pagination_class = None  

    def get_queryset(self):
        user = self.request.user

        # Venue owners see only their own events (all statuses)
        if hasattr(user, 'role') and user.is_authenticated and user.role == 'VENUE_OWNER':
            queryset = Event.objects.filter(created_by=user).order_by('id')
        # Admins see everything
        elif hasattr(user, 'role') and user.is_authenticated and user.role == 'Admin':
            queryset = Event.objects.all().order_by('id')
        # Everyone else (customers, anonymous) only sees approved events
        else:
            queryset = Event.objects.filter(status='approved').order_by('id')

        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(
                show__screen__theater__city__iexact=city
            ).distinct()
        return queryset

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        if self.action in ['add_review', 'delete_review']:
            return [IsAuthenticated()]
        return [IsVenueOwner()]

    def get_serializer_context(self):
        return {'request': self.request}

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def cities(self, request):
        """Returns list of unique cities that have active shows."""
        from theaters.models import Theater
        from django.utils import timezone
        cities = Theater.objects.filter(
            screens__shows__show_time__gte=timezone.now()
        ).values_list('city', flat=True).distinct().order_by('city')
        return Response(sorted(set(c.strip().title() for c in cities)))

    @action(detail=False, methods=['get'], permission_classes=[IsVenueOwner])
    def my_events(self, request):
        events = Event.objects.filter(created_by=request.user).order_by('id')
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def reviews(self, request, pk=None):
        event = self.get_object()
        reviews = event.reviews.all().order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_review(self, request, pk=None):
        event = self.get_object()
        if Review.objects.filter(event=event, user=request.user).exists():
            return Response(
                {'error': 'You have already reviewed this event.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = ReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(event=event, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated])
    def delete_review(self, request, pk=None):
        event = self.get_object()
        try:
            review = Review.objects.get(event=event, user=request.user)
            review.delete()
            return Response({'message': 'Review deleted.'})
        except Review.DoesNotExist:
            return Response(
                {'error': 'Review not found.'},
                status=status.HTTP_404_NOT_FOUND
            )