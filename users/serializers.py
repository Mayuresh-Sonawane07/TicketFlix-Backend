from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from .models import OTPVerification, SupportTicket, SupportMessage
from .services import generate_otp, send_otp_email

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'role', 'phone_number',
                  'location', 'is_phone_verified', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User(
            email=validated_data['email'],
            role=validated_data.get('role', 'Customer'),
            first_name=validated_data.get('first_name', ''),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class RegisterInitSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=10)
    password = serializers.CharField(min_length=6, write_only=True)
    role = serializers.ChoiceField(
        choices=['Customer', 'VENUE_OWNER'],
        default='Customer'
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    def validate_phone_number(self, value):
        # Strip +91 prefix if included
        phone = value.replace("+91", "").replace(" ", "").strip()

        if len(phone) != 10 or not phone.isdigit():
            raise serializers.ValidationError("Enter a valid 10-digit Indian phone number.")

        # Indian mobile numbers start with 6, 7, 8, or 9
        if phone[0] not in ('6', '7', '8', '9'):
            raise serializers.ValidationError(
                "Enter a valid Indian mobile number (must start with 6, 7, 8, or 9)."
            )

        # Reject obviously fake/sequential numbers
        if len(set(phone)) == 1:
            # All same digits e.g. 9999999999
            raise serializers.ValidationError("Enter a valid phone number.")

        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError(
                "This phone number is already registered. Each number can only be used once."
            )

        # Also check OTPVerification for pending registrations with same phone
        if OTPVerification.objects.filter(phone_number=phone, is_used=False).exists():
            raise serializers.ValidationError(
                "A registration is already in progress with this phone number."
            )

        return phone

    def save(self):
        email = self.validated_data['email']
        name = self.validated_data['name']
        phone = self.validated_data['phone_number']
        otp = generate_otp()

        OTPVerification.objects.filter(email=email, is_used=False).delete()

        OTPVerification.objects.create(
            phone_number=phone,
            otp=otp,
            name=name,
            email=email,
            password=make_password(self.validated_data['password']),
            role=self.validated_data['role'],
        )

        return send_otp_email(email, otp, name)


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            record = OTPVerification.objects.filter(
                email=data['email'],
                otp=data['otp'],
                is_used=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP. Please try again.")

        if record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please register again.")

        data['record'] = record
        return data

    def save(self):
        record = self.validated_data['record']

        user = User(
            email=record.email,
            phone_number=record.phone_number,
            first_name=record.name,
            is_phone_verified=True,
            role=record.role,
        )
        user.password = record.password  # already hashed
        user.save()

        record.is_used = True
        record.save()

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email.")
        return value

    def save(self):
        from .models import PasswordResetOTP
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        otp = generate_otp()

        PasswordResetOTP.objects.filter(email=email, is_used=False).delete()
        PasswordResetOTP.objects.create(email=email, otp=otp)

        return send_otp_email(email, otp, user.first_name or 'User')


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, data):
        from .models import PasswordResetOTP
        try:
            record = PasswordResetOTP.objects.filter(
                email=data['email'],
                otp=data['otp'],
                is_used=False
            ).latest('created_at')
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP. Please try again.")

        if record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please request a new one.")

        data['record'] = record
        return data

    def save(self):
        record = self.validated_data['record']
        user = User.objects.get(email=record.email)
        user.set_password(self.validated_data['new_password'])
        user.save()

        record.is_used = True
        record.save()
        return user


# ── Support Ticket Serializers ─────────────────────────────────────────────

class SupportMessageSerializer(serializers.ModelSerializer):
    admin_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ('id', 'message', 'is_from_user', 'admin_name', 'created_at')

    def get_admin_name(self, obj):
        if not obj.is_from_user and obj.sender:
            return obj.sender.first_name or 'Support'
        return None


class SupportTicketSerializer(serializers.ModelSerializer):
    messages = SupportMessageSerializer(many=True, read_only=True)
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'subject', 'status', 'created_at', 'updated_at',
            'messages', 'user_email', 'user_name', 'user_role',
        )
        read_only_fields = ('id', 'status', 'created_at', 'updated_at')

    def get_user_email(self, obj):
        return obj.user.email

    def get_user_name(self, obj):
        return obj.user.first_name or obj.user.email.split('@')[0]

    def get_user_role(self, obj):
        return obj.user.role


class SupportTicketCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=1000)

    def validate_subject(self, value):
        return value.strip()

    def validate_message(self, value):
        return value.strip()

    def save(self, user):
        ticket = SupportTicket.objects.create(
            user=user,
            subject=self.validated_data['subject'],
        )
        SupportMessage.objects.create(
            ticket=ticket,
            sender=user,
            message=self.validated_data['message'],
            is_from_user=True,
        )
        # Re-fetch with messages
        return SupportTicket.objects.prefetch_related('messages__sender').get(pk=ticket.pk)


class SupportReplySerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)

    def validate_message(self, value):
        return value.strip()