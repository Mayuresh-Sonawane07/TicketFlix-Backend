from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model, authenticate
import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from users.throttles import OTPThrottle, LoginThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    UserSerializer,
    RegisterInitSerializer,
    VerifyOTPSerializer,
    LoginSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    SupportTicketSerializer,
    SupportTicketCreateSerializer,
    SupportReplySerializer,
)

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class RegisterInitView(APIView):
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = RegisterInitSerializer(data=request.data)
        if serializer.is_valid():
            sent = serializer.save()
            if sent:
                return Response(
                    {"message": "OTP sent to your email address."},
                    status=status.HTTP_200_OK
                )
            return Response(
                {"message": "Failed to send OTP. Please check your email and try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Registration successful!",
                    "token": tokens['access'],
                    "refresh": tokens['refresh'],
                    "user": {"id": user.id, "first_name": user.first_name, "role": user.role}
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            user = authenticate(request, username=email, password=password)
            if user is None:
                return Response(
                    {"error": "Invalid email or password."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if user.is_banned:
                return Response(
                    {"error": user.ban_reason or "Your account has been banned. Contact support."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if user.is_suspended:
                from django.utils import timezone
                if user.suspended_until and user.suspended_until > timezone.now():
                    return Response(
                        {"error": f"Your account is suspended until {user.suspended_until.strftime('%d %b %Y, %I:%M %p')}."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                else:
                    user.is_suspended = False
                    user.suspended_until = None
                    user.save()

            if user.role == 'VENUE_OWNER' and not user.is_approved:
                return Response(
                    {"error": "Your venue owner account is pending admin approval. You will be notified once approved."},
                    status=status.HTTP_403_FORBIDDEN
                )
            tokens = get_tokens_for_user(user)
            return Response({
                "token": tokens['access'],
                "refresh": tokens['refresh'],
                "user": {"id": user.id, "first_name": user.first_name, "role": user.role}
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response(
                {"error": "Both old and new password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.check_password(old_password):
            return Response(
                {"error": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if len(new_password) < 6:
            return Response(
                {"error": "New password must be at least 6 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.set_password(new_password)
        request.user.save()
        return Response({"message": "Password changed successfully."})


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        password = request.data.get('password')
        if not password:
            return Response(
                {"error": "Password is required to delete account."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not request.user.check_password(password):
            return Response(
                {"error": "Incorrect password."},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.delete()
        return Response(
            {"message": "Account deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


class ResendOTPView(APIView):
    throttle_classes = [OTPThrottle]

    def post(self, request):
        from .models import OTPVerification
        from .services import generate_otp, send_otp_email

        email = request.data.get('email')
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            record = OTPVerification.objects.filter(
                email=email, is_used=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            return Response(
                {"error": "No pending registration found. Please register again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_otp = generate_otp()
        record.otp = new_otp
        from django.utils import timezone
        record.created_at = timezone.now()
        record.save()

        sent = send_otp_email(email, new_otp, record.name)
        if sent:
            return Response({"message": "OTP resent successfully."})
        return Response(
            {"message": "Failed to resend OTP."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ForgotPasswordView(APIView):
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            sent = serializer.save()
            if sent:
                return Response({"message": "OTP sent to your email."})
            return Response(
                {"error": "Failed to send OTP."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successfully!"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleLoginView(APIView):
    throttle_classes = [LoginThrottle]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required'}, status=400)
        try:
            CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(), CLIENT_ID
            )
            email = idinfo['email']
            name = idinfo.get('name', '')
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': name.split()[0] if name else '',
                    'last_name': ' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
                    'is_email_verified': True,
                    'role': 'Customer',
                }
            )
            if created:
                user.set_unusable_password()
                user.save()
            if user.is_banned:
                return Response(
                    {"error": user.ban_reason or "Your account has been banned."},
                    status=status.HTTP_403_FORBIDDEN
                )
            tokens = get_tokens_for_user(user)
            return Response({
                'token': tokens['access'],
                'refresh': tokens['refresh'],
                "user": {"id": user.id, "first_name": user.first_name, "role": user.role}
            })
        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=400)


# ── User-facing Notifications ─────────────────────────────────────────────────

class UserNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from users.models import Notification
        user = request.user

        qs = Notification.objects.filter(is_active=True).order_by('-created_at')[:50]

        result = []
        for n in qs:
            if n.target == 'all':
                result.append(n)
            elif n.target == 'customers' and user.role == 'Customer':
                result.append(n)
            elif n.target == 'venue_owners' and user.role == 'VENUE_OWNER':
                result.append(n)

        data = [{
            'id':         n.id,
            'title':      n.title,
            'message':    n.message,
            'type':       n.notif_type,
            'created_at': n.created_at,
        } for n in result]

        return Response(data)


# ── Support Ticket Views ──────────────────────────────────────────────────────

class SupportTicketListCreateView(APIView):
    """
    GET  /users/support/tickets/   → list own tickets (customers/venue owners)
                                     OR all tickets (admin)
    POST /users/support/tickets/   → create a new ticket (customers/venue owners only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import SupportTicket
        user = request.user

        if user.role == 'Admin':
            # Admin sees all tickets, newest first, with open/in_progress first
            tickets = SupportTicket.objects.prefetch_related('messages__sender').order_by(
                'status', '-created_at'
            )
        else:
            tickets = SupportTicket.objects.prefetch_related('messages__sender').filter(
                user=user
            )

        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)

    def post(self, request):
        from .models import SupportMessage
        user = request.user
        # Admins don't raise tickets
        if user.role == 'Admin':
            return Response(
                {"detail": "Admins cannot create support tickets."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SupportTicketCreateSerializer(data=request.data)
        if serializer.is_valid():
            ticket = serializer.save(user=user)

            # 🔥 CREATE FIRST MESSAGE
            message_text = request.data.get('message')

            if message_text:
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    message=message_text,
                    is_from_user=True
                )

            return Response(
                SupportTicketSerializer(ticket).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SupportTicketDetailView(APIView):
    """
    GET   /users/support/tickets/<id>/          → get ticket with messages
    PATCH /users/support/tickets/<id>/          → update status (admin only)
    """
    permission_classes = [IsAuthenticated]

    def _get_ticket(self, ticket_id, user):
        from .models import SupportTicket
        try:
            ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket_id)
        except SupportTicket.DoesNotExist:
            return None

        # Non-admins can only see their own tickets
        if user.role != 'Admin' and ticket.user != user:
            return None

        return ticket

    def get(self, request, ticket_id):
        ticket = self._get_ticket(ticket_id, request.user)
        if not ticket:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SupportTicketSerializer(ticket).data)

    def patch(self, request, ticket_id):
        # Only admins can change ticket status
        if request.user.role != 'Admin':
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        ticket = self._get_ticket(ticket_id, request.user)
        if not ticket:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid_statuses = ('open', 'in_progress', 'resolved', 'closed')
        if new_status and new_status in valid_statuses:
            ticket.status = new_status
            ticket.save()

        return Response(SupportTicketSerializer(ticket).data)


class SupportTicketReplyView(APIView):
    """
    POST /users/support/tickets/<id>/reply/
    Both users and admins can reply. Determines is_from_user by role.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        from .models import SupportTicket, SupportMessage
        user = request.user

        try:
            ticket = SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket_id)
        except SupportTicket.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Non-admins can only reply to their own tickets
        if user.role != 'Admin' and ticket.user != user:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        if ticket.status == 'closed':
            return Response(
                {"detail": "This ticket is closed and cannot receive new messages."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SupportReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        is_from_user = (user.role != 'Admin')

        msg = SupportMessage.objects.create(
            ticket=ticket,
            sender=user,
            message=serializer.validated_data['message'],
            is_from_user=is_from_user,
        )

        # When admin replies, auto-move ticket to in_progress if still open
        if not is_from_user and ticket.status == 'open':
            ticket.status = 'in_progress'
            ticket.save()

        from .serializers import SupportMessageSerializer
        return Response(
            SupportMessageSerializer(msg).data,
            status=status.HTTP_201_CREATED
        )