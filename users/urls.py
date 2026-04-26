from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.views import TokenBlacklistView
from .views import (
    UserViewSet,
    RegisterInitView,
    VerifyOTPView,
    LoginView,
    ProfileView,
    ChangePasswordView,
    DeleteAccountView,
    ResendOTPView,
    ForgotPasswordView,
    ResetPasswordView,
    GoogleLoginView,
    UserNotificationsView,
    SupportTicketListCreateView,
    SupportTicketDetailView,
    SupportTicketReplyView,
)

router = DefaultRouter()
router.register(r'', UserViewSet)

urlpatterns = [
    path('register/',         RegisterInitView.as_view(),       name='register'),
    path('verify-otp/',       VerifyOTPView.as_view(),          name='verify-otp'),
    path('resend-otp/',       ResendOTPView.as_view(),          name='resend-otp'),
    path('login/',            LoginView.as_view(),              name='login'),
    path('google-login/',     GoogleLoginView.as_view(),        name='google-login'),
    path('profile/',          ProfileView.as_view(),            name='profile'),
    path('change-password/',  ChangePasswordView.as_view(),     name='change-password'),
    path('delete-account/',   DeleteAccountView.as_view(),      name='delete-account'),
    path('forgot-password/',  ForgotPasswordView.as_view(),     name='forgot-password'),
    path('reset-password/',   ResetPasswordView.as_view(),      name='reset-password'),
    path('token/refresh/',    TokenRefreshView.as_view(),       name='token_refresh'),
    path('logout/',           TokenBlacklistView.as_view(),     name='token_blacklist'),
    path('notifications/',    UserNotificationsView.as_view(),  name='user-notifications'),

    # ── Support Tickets ──────────────────────────────────────────────────────
    path('support/tickets/',
         SupportTicketListCreateView.as_view(),
         name='support-ticket-list'),
    path('support/tickets/<int:ticket_id>/',
         SupportTicketDetailView.as_view(),
         name='support-ticket-detail'),
    path('support/tickets/<int:ticket_id>/reply/',
         SupportTicketReplyView.as_view(),
         name='support-ticket-reply'),

    path('',                  include(router.urls)),
]