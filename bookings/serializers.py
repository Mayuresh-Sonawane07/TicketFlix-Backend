from rest_framework import serializers
from .models import Booking

class BookingSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    show_details = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ('status', 'booking_time')

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    def get_show_details(self, obj):
        try:
            show = obj.show
            event = show.event
            return {
                'id': show.id,
                'show_time': show.show_time,
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'event_type': event.event_type,
                }
            }
        except Exception:
            return None