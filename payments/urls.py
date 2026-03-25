from django.urls import path
from .views import CreateOrderView, VerifyPaymentView, RazorpayWebhookView, TestRazorpayView  # ← add TestRazorpayView

urlpatterns = [
    path('create-order/', CreateOrderView.as_view(), name='create-order'),
    path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('webhook/', RazorpayWebhookView.as_view(), name='razorpay-webhook'),
    path('test-razorpay/', TestRazorpayView.as_view(), name='test-razorpay'),  # ← add this
]