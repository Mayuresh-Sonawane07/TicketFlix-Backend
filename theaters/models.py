from django.db import models
from django.conf import settings
from movies.models import Movie

class Theater(models.Model):
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Screen(models.Model):
    theater = models.ForeignKey(Theater, related_name='screens', on_delete=models.CASCADE)
    screen_number = models.IntegerField()
    total_seats = models.IntegerField()

    def __str__(self):
        return f"{self.theater.name} - Screen {self.screen_number}"

class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    screen = models.ForeignKey(Screen, related_name='shows', on_delete=models.CASCADE)
    show_time = models.DateTimeField()
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.movie.title} at {self.screen.theater.name} ({self.show_time.strftime('%Y-%m-%d %H:%M')})"

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
