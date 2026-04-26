from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'Admin')
        extra_fields.setdefault('is_approved', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = (
        ('Customer', 'Customer'),
        ('Admin', 'Admin'),
        ('VENUE_OWNER', 'Venue Owner'),
    )
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Customer')
    phone_number = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=255, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)

    # ── Admin control fields ──────────────────────────────
    is_approved = models.BooleanField(
        default=False,
        help_text='Venue owners must be approved by admin before access.'
    )
    is_banned = models.BooleanField(
        default=False,
        help_text='Banned users cannot log in at all.'
    )
    is_suspended = models.BooleanField(
        default=False,
        help_text='Suspended users can log in but have limited access.'
    )
    ban_reason = models.TextField(blank=True, null=True)
    suspended_until = models.DateTimeField(blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True, null=True)
    is_deleted = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return self.email

    @property
    def can_access_venue_dashboard(self):
        """Venue owners need approval; Admins always have access."""
        if self.role == 'Admin':
            return True
        if self.role == 'VENUE_OWNER':
            return self.is_approved and not self.is_banned
        return False


class OTPVerification(models.Model):
    phone_number = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, default='Customer')
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return (timezone.now() - self.created_at).seconds > 300

    def __str__(self):
        return f"{self.phone_number} - {self.otp}"


class PasswordResetOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return (timezone.now() - self.created_at).seconds > 300

    def __str__(self):
        return f"{self.email} - {self.otp}"


class Notification(models.Model):
    """Platform-wide notifications sent by Admin."""
    TYPE_CHOICES = (
        ('announcement', 'Announcement'),
        ('alert',        'Alert'),
        ('maintenance',  'Maintenance'),
        ('event',        'Event Alert'),
    )
    TARGET_CHOICES = (
        ('all',          'All Users'),
        ('customers',    'Customers Only'),
        ('venue_owners', 'Venue Owners Only'),
    )
    title      = models.CharField(max_length=255)
    message    = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='announcement')
    target     = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, related_name='sent_notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] {self.title}"


class AdminLog(models.Model):
    admin = models.ForeignKey('users.User', on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin.email} - {self.action} - {self.target}"


# ── Support Ticket System ─────────────────────────────────────────────────────

class SupportTicket(models.Model):
    STATUS_CHOICES = (
        ('open',        'Open'),
        ('in_progress', 'In Progress'),
        ('resolved',    'Resolved'),
        ('closed',      'Closed'),
    )
    user       = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='support_tickets'
    )
    subject    = models.CharField(max_length=200)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.subject} — {self.user.email}"


class SupportMessage(models.Model):
    ticket       = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name='messages'
    )
    sender       = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, related_name='support_messages'
    )
    message      = models.TextField()
    # True = sent by the ticket owner (customer/venue owner)
    # False = sent by an admin
    is_from_user = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        direction = "User" if self.is_from_user else "Admin"
        return f"[{direction}] Ticket #{self.ticket_id}: {self.message[:40]}"