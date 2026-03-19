from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class OTPThrottle(AnonRateThrottle):
    scope = 'otp'

class LoginThrottle(AnonRateThrottle):
    scope = 'login'

class PaymentThrottle(UserRateThrottle):
    scope = 'payment'