from django.db import models
from django.conf import settings
from events.models import Event


class Theater(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    phone_number = models.CharField(max_length=15, blank=True)
    google_maps_link = models.URLField(blank=True, null=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='theaters'
    )

    def __str__(self):
        return f"{self.name} ({self.city})"


class Screen(models.Model):
    theater = models.ForeignKey(Theater, related_name='screens', on_delete=models.CASCADE)
    screen_number = models.IntegerField()
    total_seats = models.IntegerField()

    # Per-tier pricing
    silver_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    gold_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    platinum_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Seat counts per tier
    silver_count = models.IntegerField(default=0)
    gold_count = models.IntegerField(default=0)
    platinum_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.theater.name} - Screen {self.screen_number}"


class Show(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    screen = models.ForeignKey(Screen, related_name='shows', on_delete=models.CASCADE)
    show_time = models.DateTimeField()
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.event.title} at {self.screen.theater.name} ({self.show_time.strftime('%Y-%m-%d %H:%M')})"


class Seat(models.Model):
    CATEGORY_CHOICES = (
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
    )
    screen = models.ForeignKey(Screen, related_name='seats', on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Silver')

    def __str__(self):
        return f"{self.screen} - Seat {self.seat_number} ({self.category})"