from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    user_email    = serializers.SerializerMethodField()
    show_details  = serializers.SerializerMethodField()
    qr_code_base64 = serializers.SerializerMethodField()   # ← NEW: base64 QR for PDF

    class Meta:
        model  = Booking
        fields = '__all__'
        read_only_fields = ('status', 'booking_time')

    # ── user email ────────────────────────────────────────
    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    # ── show / event / theater details ───────────────────
    def get_show_details(self, obj):
        try:
            show    = obj.show
            event   = show.event
            screen  = show.screen
            theater = screen.theater
            return {
                'id':           show.id,
                'show_time':    show.show_time,
                'theater_name': theater.name,
                'theater_city': theater.city,
                'screen_number': screen.screen_number,
                'screen_pricing': {
                    'silver':   float(screen.silver_price),
                    'gold':     float(screen.gold_price),
                    'platinum': float(screen.platinum_price),
                },
                'event': {
                    'id':         event.id,
                    'title':      event.title,
                    'event_type': event.event_type,
                    'language':   event.language,
                    'genre':      event.genre,
                },
            }
        except Exception:
            return None

    # ── QR code as base64 PNG (for PDF embed) ────────────
    def get_qr_code_base64(self, obj):
        """
        Returns a data URI string  →  "data:image/png;base64,<b64>"
        The frontend DownloadTicket.tsx can use this directly with
        doc.addImage() without fetching a URL.
        Only included for Booked status to avoid unnecessary computation.
        """
        if obj.status != 'Booked':
            return None
        try:
            import qrcode, base64
            from io import BytesIO
            from django.conf import settings

            verify_url = (
                f"{settings.FRONTEND_URL}/verify/{obj.id}"
                f"?token={obj.qr_token}"
            )
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=6,
                border=2,
            )
            qr.add_data(verify_url)
            qr.make(fit=True)
            img    = qr.make_image(fill_color="#000000", back_color="#ffffff")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            print(f"[QR SERIALIZER ERROR] {e}")
            return None