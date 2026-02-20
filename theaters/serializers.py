from rest_framework import serializers
from .models import Theater, Screen, Show, Seat
from movies.serializers import MovieSerializer

class TheaterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theater
        fields = '__all__'

class ScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screen
        fields = '__all__'

class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'

class ShowSerializer(serializers.ModelSerializer):
    movie_details = MovieSerializer(source='movie', read_only=True)
    theater_name = serializers.CharField(source='screen.theater.name', read_only=True)
    
    class Meta:
        model = Show
        fields = '__all__'
