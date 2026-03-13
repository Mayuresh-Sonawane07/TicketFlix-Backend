import random
import threading
from django.core.mail import send_mail
from django.conf import settings

def generate_otp():
    return str(random.randint(100000, 999999))

def _send_email_task(email: str, otp: str, name: str):
    try:
        send_mail(
            subject="Your TicketFlix OTP Code",
            message=f"""Hi {name},
Your OTP for TicketFlix registration is:
{otp}
This OTP is valid for 5 minutes. Do not share it with anyone.
— TicketFlix Team""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"OTP sent to {email}: {otp}")
    except Exception as e:
        print(f"Email error: {str(e)}")

def send_otp_email(email: str, otp: str, name: str) -> bool:
    thread = threading.Thread(target=_send_email_task, args=(email, otp, name))
    thread.daemon = True
    thread.start()
    return True