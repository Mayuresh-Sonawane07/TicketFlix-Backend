from django.db import models
from django.conf import settings
from theaters.models import Show, Seat
from django.utils import timezone
from datetime import timedelta
import uuid


class Booking(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Booked', 'Booked'),
        ('Cancelled', 'Cancelled'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    seats = models.ManyToManyField(Seat)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Booked')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    booking_time = models.DateTimeField(auto_now_add=True)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checked_in = models.BooleanField(default=False)
    checked_in_time = models.DateTimeField(null=True, blank=True)

    def is_cancellable(self):
        now = timezone.now()
        time_diff = self.show.show_time - now
        return time_diff >= timedelta(hours=24) and self.status != 'Cancelled'

    def __str__(self):
        return f"Booking {self.id} by {self.user.email} for {self.show}"