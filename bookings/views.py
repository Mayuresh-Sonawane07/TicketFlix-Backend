from rest_framework import viewsets, status  # noqa
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking
from .serializers import BookingSerializer


def send_booking_confirmation(booking):
    """Send booking confirmation email to customer."""
    try:
        show = booking.show
        event = show.event
        screen = show.screen
        theater = screen.theater

        seat_numbers = ', '.join([s.seat_number for s in booking.seats.all()])
        show_time = show.show_time.strftime('%A, %d %B %Y at %I:%M %p')

        subject = f'Booking Confirmed – {event.title} | TicketFlix #{booking.id}'

        html_message = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Booking Confirmed</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0f;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#dc2626;padding:28px 32px;border-radius:12px 12px 0 0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <h1 style="margin:0;color:#fff;font-size:26px;font-weight:bold;">TicketFlix</h1>
                    <p style="margin:4px 0 0;color:#fca5a5;font-size:13px;">Your Official Booking Confirmation</p>
                  </td>
                  <td align="right">
                    <span style="background:rgba(255,255,255,0.2);color:#fff;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:bold;">CONFIRMED ✓</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#14141e;padding:32px;border-left:1px solid #2a2a3a;border-right:1px solid #2a2a3a;">

              <p style="margin:0 0 24px;color:#9ca3af;font-size:15px;">
                Hi <strong style="color:#fff;">{booking.user.get_full_name() or booking.user.email}</strong>,<br>
                Your booking is confirmed! Here are your ticket details:
              </p>

              <!-- Event Card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:10px;margin-bottom:24px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <span style="background:#dc2626;color:#fff;font-size:10px;font-weight:bold;padding:3px 10px;border-radius:4px;text-transform:uppercase;">{event.event_type}</span>
                    <h2 style="margin:10px 0 4px;color:#fff;font-size:22px;">{event.title}</h2>
                    <p style="margin:0;color:#6b7280;font-size:13px;">{event.language or ''} {('· ' + str(event.duration) + ' min') if event.duration else ''}</p>
                  </td>
                </tr>
                <tr>
                  <td style="border-top:1px dashed #2a2a3a;padding:16px 24px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding-right:16px;">
                          <p style="margin:0 0 4px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Date & Time</p>
                          <p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{show_time}</p>
                        </td>
                        <td>
                          <p style="margin:0 0 4px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Venue</p>
                          <p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{theater.name}</p>
                          <p style="margin:2px 0 0;color:#6b7280;font-size:12px;">{theater.city}</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Info Grid -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                <tr>
                  <td width="33%" style="padding-right:8px;">
                    <div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
                      <p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Booking ID</p>
                      <p style="margin:0;color:#fff;font-size:16px;font-weight:bold;">#{booking.id}</p>
                    </div>
                  </td>
                  <td width="33%" style="padding:0 4px;">
                    <div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
                      <p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Seats</p>
                      <p style="margin:0;color:#fff;font-size:14px;font-weight:bold;">{seat_numbers}</p>
                    </div>
                  </td>
                  <td width="33%" style="padding-left:8px;">
                    <div style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:8px;padding:14px;text-align:center;">
                      <p style="margin:0 0 4px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Amount Paid</p>
                      <p style="margin:0;color:#dc2626;font-size:16px;font-weight:bold;">₹{booking.total_amount}</p>
                    </div>
                  </td>
                </tr>
              </table>

              {f'<p style="margin:0 0 24px;color:#4b5563;font-size:12px;text-align:center;">Transaction ID: {booking.transaction_id}</p>' if booking.transaction_id else ''}

              <!-- Note -->
              <div style="background:#1e2a1e;border:1px solid #166534;border-radius:8px;padding:16px;">
                <p style="margin:0;color:#86efac;font-size:13px;">
                  ✅ Please carry this email or your booking ID to the venue.<br>
                  <span style="color:#4b5563;font-size:12px;margin-top:4px;display:block;">You can also download your ticket from the TicketFlix app under My Bookings.</span>
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0f0f17;padding:20px 32px;border-radius:0 0 12px 12px;border:1px solid #2a2a3a;border-top:none;text-align:center;">
              <p style="margin:0 0 4px;color:#dc2626;font-size:14px;font-weight:bold;">TicketFlix</p>
              <p style="margin:0;color:#4b5563;font-size:12px;">This is an automated email. Please do not reply.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        plain_message = f"""
Booking Confirmed – TicketFlix

Hi {booking.user.get_full_name() or booking.user.email},

Your booking is confirmed!

Event: {event.title}
Show Time: {show_time}
Venue: {theater.name}, {theater.city}
Seats: {seat_numbers}
Booking ID: #{booking.id}
Amount Paid: ₹{booking.total_amount}
{f'Transaction ID: {booking.transaction_id}' if booking.transaction_id else ''}

Please carry this email or your booking ID to the venue.

– TicketFlix Team
"""

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"[EMAIL] Booking confirmation sent to {booking.user.email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send booking confirmation: {e}")


def send_cancellation_email(booking):
    """Send cancellation confirmation email to customer."""
    try:
        show = booking.show
        event = show.event
        screen = show.screen
        theater = screen.theater

        seat_numbers = ', '.join([s.seat_number for s in booking.seats.all()])
        show_time = show.show_time.strftime('%A, %d %B %Y at %I:%M %p')

        subject = f'Booking Cancelled – {event.title} | TicketFlix #{booking.id}'

        html_message = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0f;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#374151;padding:28px 32px;border-radius:12px 12px 0 0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <h1 style="margin:0;color:#fff;font-size:26px;font-weight:bold;">TicketFlix</h1>
                    <p style="margin:4px 0 0;color:#d1d5db;font-size:13px;">Booking Cancellation Notice</p>
                  </td>
                  <td align="right">
                    <span style="background:rgba(239,68,68,0.3);color:#fca5a5;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:bold;">CANCELLED</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#14141e;padding:32px;border-left:1px solid #2a2a3a;border-right:1px solid #2a2a3a;">
              <p style="margin:0 0 24px;color:#9ca3af;font-size:15px;">
                Hi <strong style="color:#fff;">{booking.user.get_full_name() or booking.user.email}</strong>,<br>
                Your booking has been successfully cancelled.
              </p>

              <!-- Cancelled Booking Details -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#1e1e2e;border:1px solid #2a2a3a;border-radius:10px;margin-bottom:24px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <h2 style="margin:0 0 4px;color:#9ca3af;font-size:20px;text-decoration:line-through;">{event.title}</h2>
                    <p style="margin:4px 0 0;color:#6b7280;font-size:13px;">{show_time}</p>
                    <p style="margin:4px 0 0;color:#6b7280;font-size:13px;">{theater.name}, {theater.city}</p>
                  </td>
                </tr>
                <tr>
                  <td style="border-top:1px solid #2a2a3a;padding:16px 24px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td>
                          <p style="margin:0 0 2px;color:#6b7280;font-size:11px;">Booking ID</p>
                          <p style="margin:0;color:#9ca3af;font-size:14px;">#{booking.id}</p>
                        </td>
                        <td>
                          <p style="margin:0 0 2px;color:#6b7280;font-size:11px;">Seats</p>
                          <p style="margin:0;color:#9ca3af;font-size:14px;">{seat_numbers}</p>
                        </td>
                        <td>
                          <p style="margin:0 0 2px;color:#6b7280;font-size:11px;">Amount</p>
                          <p style="margin:0;color:#9ca3af;font-size:14px;">₹{booking.total_amount}</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Refund Note -->
              <div style="background:#1e1a14;border:1px solid #78350f;border-radius:8px;padding:16px;">
                <p style="margin:0;color:#fcd34d;font-size:13px;">
                  💰 Refund Info: If you paid online, your refund will be processed to your original payment method within 5–7 business days.
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0f0f17;padding:20px 32px;border-radius:0 0 12px 12px;border:1px solid #2a2a3a;border-top:none;text-align:center;">
              <p style="margin:0 0 4px;color:#dc2626;font-size:14px;font-weight:bold;">TicketFlix</p>
              <p style="margin:0;color:#4b5563;font-size:12px;">This is an automated email. Please do not reply.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        plain_message = f"""
Booking Cancelled – TicketFlix

Hi {booking.user.get_full_name() or booking.user.email},

Your booking has been cancelled.

Event: {event.title}
Show Time: {show_time}
Venue: {theater.name}, {theater.city}
Seats: {seat_numbers}
Booking ID: #{booking.id}
Amount: ₹{booking.total_amount}

If you paid online, your refund will be processed within 5-7 business days.

– TicketFlix Team
"""

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"[EMAIL] Cancellation email sent to {booking.user.email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send cancellation email: {e}")


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
            request.data['status'] = 'Pending'
            request.data['user'] = request.user.id
            return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def venue_analytics(self, request):
        user = request.user
        if user.role != 'VENUE_OWNER':
            return Response(
                {"error": "Only venue owners can access analytics."},
                status=status.HTTP_403_FORBIDDEN
            )
        bookings = Booking.objects.filter(
            show__event__created_by=user
        ).select_related('show', 'show__event', 'show__screen', 'show__screen__theater', 'user').prefetch_related('seats')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        booking = self.get_object()
        if booking.user != request.user:
            return Response(
                {"error": "Unauthorized."},
                status=status.HTTP_403_FORBIDDEN
            )
        if booking.status == 'Booked':
            return Response({"message": "Already confirmed."})

        booking.status = 'Booked'
        booking.transaction_id = request.data.get('transaction_id', f"TXN-{booking.id}")
        booking.save()

        # Send confirmation email
        send_booking_confirmation(booking)

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

            # Send cancellation email
            send_cancellation_email(booking)

            return Response({'status': 'Booking cancelled successfully.'})
        return Response(
            {'error': 'Cannot cancel. Less than 24 hours to showtime or already cancelled.'},
            status=status.HTTP_400_BAD_REQUEST
        )