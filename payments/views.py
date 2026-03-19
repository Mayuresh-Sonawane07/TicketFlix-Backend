import razorpay
import hmac
import hashlib
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from bookings.models import Booking
from bookings.serializers import BookingSerializer
from bookings.views import send_booking_confirmation
from theaters.models import Show, Seat
from django.db import transaction

client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        show_id = request.data.get('show')
        seat_ids = request.data.get('seats', [])

        if not show_id or not seat_ids:
            return Response(
                {"error": "Show and seats are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from bookings.views import release_expired_pending_bookings
        release_expired_pending_bookings()

        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response(
                {"error": "Show not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        already_booked = Booking.objects.filter(
            show_id=show_id,
            status='Booked',
            seats__in=seat_ids
        ).exists()

        if already_booked:
            return Response(
                {"error": "One or more seats are already booked."},
                status=status.HTTP_400_BAD_REQUEST
            )

        seats = Seat.objects.filter(id__in=seat_ids)
        screen = show.screen
        ticket_amount = 0.0
        seat_breakdown = []
        for seat in seats:
            if seat.category == 'Silver':
                price = float(screen.silver_price)
            elif seat.category == 'Gold':
                price = float(screen.gold_price)
            elif seat.category == 'Platinum':
                price = float(screen.platinum_price)
            else:
                price = float(show.price)
            ticket_amount += price
            seat_breakdown.append({'seat': seat.seat_number, 'type': seat.category, 'price': price})

        num_seats = len(seat_ids)
        convenience_fee = round(ticket_amount * settings.CONVENIENCE_FEE_PERCENT / 100, 2)
        total_amount = round(ticket_amount + convenience_fee, 2)

        razorpay_order = client.order.create({
            "amount": int(total_amount * 100),
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "show_id": str(show_id),
                "seat_ids": ",".join(map(str, seat_ids)),
                "user_id": str(request.user.id),
            }
        })

        return Response({
            "order_id": razorpay_order["id"],
            "amount": total_amount,
            "ticket_amount": ticket_amount,
            "convenience_fee": convenience_fee,
            "num_seats": num_seats,
            "seat_breakdown": seat_breakdown,
            "key_id": settings.RAZORPAY_KEY_ID,
            "currency": "INR",
        })


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        show_id = request.data.get('show')
        seat_ids = request.data.get('seats', [])
        total_amount = request.data.get('total_amount')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response(
                {"error": "Payment details missing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify signature
        try:
            generated_signature = hmac.new(
                key=settings.RAZORPAY_KEY_SECRET.encode(),
                msg=f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
                digestmod=hashlib.sha256
            ).hexdigest()

            if generated_signature != razorpay_signature:
                return Response(
                    {"error": "Payment verification failed. Invalid signature."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception:
            return Response(
                {"error": "Signature verification error."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create booking after successful verification
        with transaction.atomic():
            already_booked = Booking.objects.filter(
                show_id=show_id,
                status='Booked',
                seats__in=seat_ids
            ).exists()

            if already_booked:
                return Response(
                    {"error": "Seats were booked by someone else. Please select different seats."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            booking = Booking.objects.create(
                user=request.user,
                show_id=show_id,
                total_amount=total_amount,
                status='Booked',
                transaction_id=razorpay_payment_id,
            )
            booking.seats.set(seat_ids)
            booking.save()

        # Send confirmation email (outside transaction so booking is committed first)
        send_booking_confirmation(booking)

        return Response({
            "message": "Payment verified and booking confirmed!",
            "booking": BookingSerializer(booking).data,
        }, status=status.HTTP_201_CREATED)