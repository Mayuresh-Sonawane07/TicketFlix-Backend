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

        num_seats = len(seat_ids)
        ticket_amount = float(show.price) * num_seats
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
            "show_price": float(show.price),
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


import json
from rest_framework.permissions import AllowAny

class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Step 1: Verify webhook signature
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        webhook_signature = request.headers.get('X-Razorpay-Signature', '')

        try:
            generated_signature = hmac.new(
                key=webhook_secret.encode(),
                msg=request.body,
                digestmod=hashlib.sha256
            ).hexdigest()

            if generated_signature != webhook_signature:
                print("[WEBHOOK] Invalid signature — possible fake request")
                return Response({"error": "Invalid signature"}, status=400)
        except Exception as e:
            print(f"[WEBHOOK] Signature error: {e}")
            return Response({"error": "Signature error"}, status=400)

        # Step 2: Parse event
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=400)

        event = payload.get('event')
        print(f"[WEBHOOK] Received event: {event}")

        # Step 3: Handle payment.captured
        if event == 'payment.captured':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            razorpay_payment_id = payment_entity.get('id')
            razorpay_order_id = payment_entity.get('order_id')
            notes = payment_entity.get('notes', {})

            show_id = notes.get('show_id')
            seat_ids_str = notes.get('seat_ids', '')
            user_id = notes.get('user_id')

            if not all([show_id, seat_ids_str, user_id]):
                print("[WEBHOOK] Missing notes data")
                return Response({"status": "ok"})

            # Check if booking already exists (created by frontend verify)
            if Booking.objects.filter(transaction_id=razorpay_payment_id).exists():
                print(f"[WEBHOOK] Booking already exists for payment {razorpay_payment_id}")
                return Response({"status": "ok"})

            # Create booking if not exists (fallback for browser crash cases)
            try:
                seat_ids = [int(sid) for sid in seat_ids_str.split(',') if sid.strip()]
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=int(user_id))

                # Calculate total amount from Razorpay (in paise, convert to rupees)
                total_amount = payment_entity.get('amount', 0) / 100

                with transaction.atomic():
                    already_booked = Booking.objects.filter(
                        show_id=show_id,
                        status='Booked',
                        seats__in=seat_ids
                    ).exists()

                    if already_booked:
                        print(f"[WEBHOOK] Seats already booked for show {show_id}")
                        return Response({"status": "ok"})

                    booking = Booking.objects.create(
                        user=user,
                        show_id=show_id,
                        total_amount=total_amount,
                        status='Booked',
                        transaction_id=razorpay_payment_id,
                    )
                    booking.seats.set(seat_ids)
                    booking.save()

                print(f"[WEBHOOK] Booking {booking.id} created via webhook for payment {razorpay_payment_id}")
                send_booking_confirmation(booking)

            except Exception as e:
                print(f"[WEBHOOK] Error creating booking: {e}")

        # Step 4: Handle payment.failed
        elif event == 'payment.failed':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            print(f"[WEBHOOK] Payment failed: {payment_entity.get('id')} — releasing any pending seats")
            # Pending bookings are auto-released by release_expired_pending_bookings()
            # so no action needed here

        return Response({"status": "ok"})