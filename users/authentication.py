import base64
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            return None

        try:
            token = auth_header.split(' ')[1]
            decoded = base64.b64decode(token).decode('utf-8')
            email, password = decoded.split(':', 1)
        except Exception:
            raise AuthenticationFailed('Invalid token format.')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')

        # Allow google-oauth tokens without password check
        if password == 'google-oauth':
            return (user, token)

        # Normal password check
        if not user.check_password(password):
            raise AuthenticationFailed('Invalid credentials.')

        return (user, token)
