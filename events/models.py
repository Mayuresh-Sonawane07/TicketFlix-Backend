import os
import uuid
from django.db import models
from django.conf import settings

def event_image_upload_path(instance, filename):
    ext = filename.split('.')[-1]  # get file extension
    filename = f"{uuid.uuid4()}.{ext}"  # generate short unique name
    return f"events/{filename}"

class Event(models.Model):
    EVENT_TYPE_CHOICES = (
        ('MOVIE', 'Movie'),
        ('CONCERT', 'Concert'),
        ('SPORTS', 'Sports'),
        ('OTHER', 'Other'),
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    duration = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=100, blank=True)
    genre = models.CharField(max_length=100, blank=True)
    release_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'VENUE_OWNER'}
    )
    image = models.ImageField(upload_to=event_image_upload_path, null=True, blank=True)  # ✅ fixed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.event_type})"

class Review(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')  # one review per user per event

    def __str__(self):
        return f"{self.user.email} rated {self.event.title} {self.rating}/5"