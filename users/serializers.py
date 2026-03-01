from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from .models import OTPVerification
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
        phone = value.replace("+91", "").strip()
        if len(phone) != 10 or not phone.isdigit():
            raise serializers.ValidationError("Enter a valid 10-digit phone number.")
        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError("Phone number already registered.")
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