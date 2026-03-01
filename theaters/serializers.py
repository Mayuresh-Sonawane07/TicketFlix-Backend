from rest_framework import serializers
from .models import Theater, Screen, Show, Seat
from events.serializers import EventSerializer


class TheaterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theater
        fields = '__all__'
        read_only_fields = ['manager']

    def create(self, validated_data):
        validated_data['manager'] = self.context['request'].user
        return super().create(validated_data)


class ScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screen
        fields = '__all__'


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'


class ShowSerializer(serializers.ModelSerializer):
    event_details = EventSerializer(source='event', read_only=True)
    theater_name = serializers.CharField(source='screen.theater.name', read_only=True)
    screen_number = serializers.IntegerField(source='screen.screen_number', read_only=True)
    screen_pricing = serializers.SerializerMethodField()

    class Meta:
        model = Show
        fields = '__all__'

    def get_screen_pricing(self, obj):
        return {
            'silver': float(obj.screen.silver_price),
            'gold': float(obj.screen.gold_price),
            'platinum': float(obj.screen.platinum_price),
        }