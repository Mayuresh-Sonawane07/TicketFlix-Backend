import random
from django.core.mail import send_mail
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(email: str, otp: str, name: str) -> bool:
    try:
        send_mail(
            subject="Your TicketFlix OTP Code",
            message=f"""
Hi {name},

Your OTP for TicketFlix registration is:

{otp}

This OTP is valid for 5 minutes. Do not share it with anyone.

If you did not request this, please ignore this email.

— TicketFlix Team
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"\n{'='*40}")
        print(f"📧 OTP sent to {email}: {otp}")
        print(f"{'='*40}\n")
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False