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

        # Fetch active notifications, filter by target role
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