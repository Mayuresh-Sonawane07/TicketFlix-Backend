from django.urls import path
from .views import CreateOrderView, VerifyPaymentView, RazorpayWebhookView

urlpatterns = [
    path('create-order/', CreateOrderView.as_view(), name='create-order'),
    path('verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('webhook/', RazorpayWebhookView.as_view()),
]