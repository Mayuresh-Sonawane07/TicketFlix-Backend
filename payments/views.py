import razorpay
import hmac
import hashlib
import json
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.contrib.auth import get_user_model

from bookings.models import Booking
from bookings.serializers import BookingSerializer
from bookings.views import send_booking_confirmation
from theaters.models import Show

client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# ✅ CREATE ORDER
class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print("=== CREATE ORDER START ===")
        show_id = request.data.get('show')
        seat_ids = request.data.get('seats', [])
        print(f"show_id: {show_id}, seat_ids: {seat_ids}")

        if not show_id or not seat_ids:
            return Response({"error": "Show and seats are required."}, status=400)

        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response({"error": "Show not found."}, status=404)

        if Booking.objects.filter(
            show_id=show_id,
            status='Booked',
            seats__in=seat_ids
        ).exists():
            return Response({"error": "Seats already booked."}, status=400)

        num_seats = len(seat_ids)
        ticket_amount = float(show.price) * num_seats
        convenience_fee = round(ticket_amount * settings.CONVENIENCE_FEE_PERCENT / 100, 2)
        total_amount = round(ticket_amount + convenience_fee, 2)

        print("=== CALLING RAZORPAY ===")
        try:
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
            print(f"=== RAZORPAY SUCCESS: {razorpay_order['id']} ===")
        except requests.exceptions.Timeout:
            print("=== RAZORPAY TIMEOUT ===")
            return Response({"error": "Payment service timeout. Please try again."}, status=503)
        except requests.exceptions.ConnectionError as e:
            print(f"=== RAZORPAY CONNECTION ERROR: {e} ===")
            return Response({"error": "Payment service unreachable. Please try again."}, status=503)
        except Exception as e:
            print(f"=== RAZORPAY FAILED: {e} ===")
            return Response({"error": "Failed to create payment order."}, status=500)

        print("=== CREATE ORDER DONE ===")
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
        
# ✅ VERIFY PAYMENT (ONLY VERIFY — NO BOOKING)
class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response({"error": "Payment details missing."}, status=400)

        try:
            generated_signature = hmac.new(
                key=settings.RAZORPAY_KEY_SECRET.encode(),
                msg=f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
                digestmod=hashlib.sha256
            ).hexdigest()

            if generated_signature != razorpay_signature:
                return Response({"error": "Invalid payment signature."}, status=400)

        except Exception as e:
            print("VERIFY ERROR:", str(e))
            return Response({"error": "Verification failed."}, status=400)

        return Response({"message": "Payment verified successfully!"}, status=200)


# ✅ WEBHOOK (CREATES BOOKING)
class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        signature = request.headers.get('X-Razorpay-Signature', '')

        # Verify webhook signature
        generated_signature = hmac.new(
            key=webhook_secret.encode(),
            msg=request.body,
            digestmod=hashlib.sha256
        ).hexdigest()

        if generated_signature != signature:
            return Response({"error": "Invalid signature"}, status=400)

        payload = json.loads(request.body)
        event = payload.get('event')

        print(f"[WEBHOOK] Event: {event}")

        if event == 'payment.captured':
            payment = payload['payload']['payment']['entity']

            payment_id = payment.get('id')
            notes = payment.get('notes', {})

            show_id = notes.get('show_id')
            seat_ids = [int(s) for s in notes.get('seat_ids', '').split(',') if s]
            user_id = notes.get('user_id')

            if Booking.objects.filter(transaction_id=payment_id).exists():
                return Response({"status": "already exists"})

            User = get_user_model()
            user = User.objects.get(id=user_id)

            total_amount = payment.get('amount', 0) / 100

            with transaction.atomic():
                if Booking.objects.filter(
                    show_id=show_id,
                    status='Booked',
                    seats__in=seat_ids
                ).exists():
                    return Response({"status": "seats taken"})

                booking = Booking.objects.create(
                    user=user,
                    show_id=show_id,
                    total_amount=total_amount,
                    status='Booked',
                    transaction_id=payment_id,
                )
                booking.seats.set(seat_ids)

            print(f"[WEBHOOK] Booking created: {booking.id}")
            send_booking_confirmation(booking)

        return Response({"status": "ok"})

class TestRazorpayView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        import requests, socket
        try:
            r = requests.get("https://api.razorpay.com", timeout=5)
            return Response({
                "reachable": True,
                "code": r.status_code,
                "server_ip": socket.gethostbyname(socket.gethostname())
            })
        except Exception as e:
            return Response({"reachable": False, "error": str(e)})