from django.db import models

class Movie(models.Model):
    STATUS_CHOICES = (
        ('Now Showing', 'Now Showing'),
        ('Coming Soon', 'Coming Soon'),
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    duration = models.IntegerField(help_text="Duration in minutes")
    language = models.CharField(max_length=50)
    genre = models.CharField(max_length=100)
    release_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Now Showing')

    def __str__(self):
        return self.title
