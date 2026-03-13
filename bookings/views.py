from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
import qrcode
import base64
from io import BytesIO
from .models import Booking
from .serializers import BookingSerializer


def generate_qr_base64(booking):
    verify_url = f"{settings.FRONTEND_URL}/verify/{booking.id}?token={booking.qr_token}"
    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=6, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8'), verify_url


def send_booking_confirmation(booking):
    try:
        show = booking.show
        event = show.event
        screen = show.screen
        theater = screen.theater
        seat_numbers = ', '.join([s.seat_number for s in booking.seats.all()])
        show_time = show.show_time.strftime('%A, %d %B %Y at %I:%M %p')
        qr_base64, verify_url = generate_qr_base64(booking)
        subject = f'Booking Confirmed - {event.title} | TicketFlix #{booking.id}'
        html_message = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0f;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="background:#dc2626;padding:28px 32px;border-radius:12px 12px 0 0;">
<table width="100%"><tr>
<td><h1 style="margin:0;color:#fff;font-size:26px;">TicketFlix</h1>
<p style="margin:4px 0 0;color:#fca5a5;font-size:13px;">Your Official Booking Confirmation</p></td>
<td align="right"><span style="background:rgba(255,255,255,0.2);color:#fff;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:bold;">CONFIRMED</span></td>
</tr></table></td></tr>
<tr><td style="background:#14141e;padding:32px;border-left:1px solid #2a2a3a;border-right:1px solid #2a2a3a;">
<p style="color:#9ca3af;font-size:15px;">Hi <strong style="color:#fff;">{booking.user.email}</strong>,<br>Your booking is confirmed! Show the QR code at entry.</p>
<table width="100%" style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:10px;margin-bottom:24px;">
<tr><td style="padding:20px 24px;">
<span style="background:#dc2626;color:#fff;font-size:10px;font-weight:bold;padding:3px 10px;border-radius:4px;">{event.event_type}</span>
<h2 style="margin:10px 0 4px;color:#fff;font-size:22px;">{event.title}</h2>
</td></tr>
<tr><td style="border-top:1px dashed #2a2a3a;padding:16px 24px;">
<table width="100%"><tr>
<td><p style="margin:0 0 4px;color:#6b7280;font-size:11px;text-transform:uppercase;">Date &amp; Time</p>
<p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{show_time}</p></td>
<td><p style="margin:0 0 4px;color:#6b7280;font-size:11px;text-transform:uppercase;">Venue</p>
<p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{theater.name}, {theater.city}</p></td>
</tr></table>
</td></tr></table>
<table width="100%" style="margin-bottom:24px;"><tr>
<td width="33%" style="padding-right:8px;"><div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
<p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;">Booking ID</p>
<p style="margin:0;color:#fff;font-size:16px;font-weight:bold;">#{booking.id}</p></div></td>
<td width="33%" style="padding:0 4px;"><div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
<p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;">Seats</p>
<p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{seat_numbers}</p></div></td>
<td width="33%" style="padding-left:8px;"><div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
<p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;">Amount Paid</p>
<p style="margin:0;color:#dc2626;font-size:16px;font-weight:bold;">Rs.{booking.total_amount}</p></div></td>
</tr></table>
<table width="100%" style="margin-bottom:24px;"><tr>
<td align="center" style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:10px;padding:24px;">
<p style="margin:0 0 16px;color:#9ca3af;font-size:13px;font-weight:bold;text-transform:uppercase;">Scan at Entry</p>
<img src="data:image/png;base64,{qr_base64}" width="160" height="160" alt="QR Code" style="display:block;margin:0 auto;border-radius:8px;" />
<p style="margin:12px 0 0;color:#4b5563;font-size:11px;">#TF{str(booking.id).zfill(6)}</p>
</td></tr></table>
</td></tr>
<tr><td style="background:#0f0f17;padding:20px 32px;border-radius:0 0 12px 12px;border:1px solid #2a2a3a;border-top:none;text-align:center;">
<p style="margin:0 0 4px;color:#dc2626;font-size:14px;font-weight:bold;">TicketFlix</p>
<p style="margin:0;color:#4b5563;font-size:12px;">This is an automated email. Please do not reply.</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
        plain_message = f"Booking Confirmed - {event.title}\nBooking #{booking.id}\nShow: {show_time}\nVenue: {theater.name}, {theater.city}\nSeats: {seat_numbers}\nAmount: Rs.{booking.total_amount}\nVerify: {verify_url}"
        send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [booking.user.email], html_message=html_message, fail_silently=False)
        print(f"[EMAIL] Confirmation sent to {booking.user.email}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


def send_cancellation_email(booking):
    try:
        show = booking.show
        event = show.event
        theater = show.screen.theater
        seat_numbers = ', '.join([s.seat_number for s in booking.seats.all()])
        show_time = show.show_time.strftime('%A, %d %B %Y at %I:%M %p')
        subject = f'Booking Cancelled - {event.title} | TicketFlix #{booking.id}'
        html_message = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0f;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="background:#374151;padding:28px 32px;border-radius:12px 12px 0 0;">
<table width="100%"><tr>
<td><h1 style="margin:0;color:#fff;font-size:26px;">TicketFlix</h1>
<p style="margin:4px 0 0;color:#d1d5db;font-size:13px;">Booking Cancellation Notice</p></td>
<td align="right"><span style="background:rgba(239,68,68,0.3);color:#fca5a5;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:bold;">CANCELLED</span></td>
</tr></table></td></tr>
<tr><td style="background:#14141e;padding:32px;border-left:1px solid #2a2a3a;border-right:1px solid #2a2a3a;">
<p style="color:#9ca3af;">Hi <strong style="color:#fff;">{booking.user.email}</strong>, your booking has been cancelled.</p>
<table width="100%" style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:10px;margin-bottom:24px;">
<tr><td style="padding:20px 24px;">
<h2 style="margin:0 0 4px;color:#9ca3af;font-size:20px;text-decoration:line-through;">{event.title}</h2>
<p style="margin:4px 0 0;color:#6b7280;">{show_time} | {theater.name}, {theater.city}</p>
<p style="margin:4px 0 0;color:#6b7280;">Seats: {seat_numbers} | Booking #{booking.id} | Rs.{booking.total_amount}</p>
</td></tr></table>
<div style="background:#1e1a14;border:1px solid #78350f;border-radius:8px;padding:16px;">
<p style="margin:0;color:#fcd34d;font-size:13px;">Refund will be processed within 5-7 business days.</p>
</div>
</td></tr>
<tr><td style="background:#0f0f17;padding:20px 32px;border-radius:0 0 12px 12px;border:1px solid #2a2a3a;border-top:none;text-align:center;">
<p style="margin:0;color:#dc2626;font-size:14px;font-weight:bold;">TicketFlix</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
        plain_message = f"Booking Cancelled - {event.title}\nBooking #{booking.id}\nSeats: {seat_numbers}\nRefund within 5-7 business days."
        send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [booking.user.email], html_message=html_message, fail_silently=False)
        print(f"[EMAIL] Cancellation sent to {booking.user.email}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if user.role == "Admin":
            return Booking.objects.all()
        return Booking.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        if request.user.role != "Customer":
            return Response({"error": "Only customers can book tickets."}, status=status.HTTP_403_FORBIDDEN)
        seat_ids = request.data.get('seats', [])
        show_id = request.data.get('show')
        if not seat_ids or not show_id:
            return Response({"error": "Show and seats are required."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            existing = Booking.objects.filter(show_id=show_id, status='Booked', seats__in=seat_ids)
            if existing.exists():
                return Response({'error': 'One or more seats are already booked.'}, status=status.HTTP_400_BAD_REQUEST)
            request.data['status'] = 'Pending'
            request.data['user'] = request.user.id
            return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def venue_analytics(self, request):
        user = request.user
        if user.role != 'VENUE_OWNER':
            return Response({"error": "Only venue owners can access analytics."}, status=status.HTTP_403_FORBIDDEN)
        bookings = Booking.objects.filter(
            show__event__created_by=user
        ).select_related('show', 'show__event', 'show__screen', 'show__screen__theater', 'user').prefetch_related('seats')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        booking = self.get_object()
        if booking.user != request.user:
            return Response({"error": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)
        if booking.status == 'Booked':
            return Response({"message": "Already confirmed."})
        booking.status = 'Booked'
        booking.transaction_id = request.data.get('transaction_id', f"TXN-{booking.id}")
        booking.save()
        send_booking_confirmation(booking)
        return Response({"message": "Payment confirmed! Booking successful.", "booking": BookingSerializer(booking).data})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.user != request.user:
            return Response({"error": "You can only cancel your own booking."}, status=status.HTTP_403_FORBIDDEN)
        if booking.is_cancellable():
            booking.status = 'Cancelled'
            booking.save()
            send_cancellation_email(booking)
            return Response({'status': 'Booking cancelled successfully.'})
        return Response({'error': 'Cannot cancel. Less than 24 hours to showtime or already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], permission_classes=[AllowAny])
    def verify(self, request, pk=None):
        token = request.query_params.get('token')
        if not token:
            return Response({'valid': False, 'reason': 'No token provided'}, status=400)

        try:
            booking = Booking.objects.get(id=pk, qr_token=token)
        except Booking.DoesNotExist:
            return Response({'valid': False, 'reason': 'Invalid ticket'}, status=404)

        if booking.status != 'Booked':
            return Response({
                'valid': False,
                'reason': f'Booking is {booking.status}',
                'status': booking.status,
                'checked_in': booking.checked_in,
                'checked_in_time': booking.checked_in_time,
            })

        # POST = mark as used
        if request.method == 'POST':
            if booking.checked_in:
                return Response({
                    'valid': False,
                    'already_used': True,
                    'reason': 'Ticket already used',
                    'checked_in_time': booking.checked_in_time,
                    'event': booking.show.event.title,
                    'show_time': booking.show.show_time,
                    'seats': [s.seat_number for s in booking.seats.all()],
                })
            from django.utils import timezone
            booking.checked_in = True
            booking.checked_in_time = timezone.now()
            booking.save()
            return Response({'valid': True, 'marked_used': True, 'checked_in_time': booking.checked_in_time})

        # GET = just verify
        return Response({
            'valid': True,
            'status': booking.status,
            'checked_in': booking.checked_in,
            'checked_in_time': booking.checked_in_time,
            'event': booking.show.event.title,
            'event_type': booking.show.event.event_type,
            'show_time': booking.show.show_time,
            'venue': booking.show.screen.theater.name,
            'seats': [s.seat_number for s in booking.seats.all()],
            'customer': booking.user.get_full_name() or booking.user.email,
            'total_amount': str(booking.total_amount),
        })