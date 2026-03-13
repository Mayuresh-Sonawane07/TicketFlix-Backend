import random
import threading
import resend
from django.conf import settings

def generate_otp():
    return str(random.randint(100000, 999999))

def _send_email_task(email: str, otp: str, name: str):
    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": "TicketFlix <onboarding@resend.dev>",
            "to": [email],
            "subject": "Your TicketFlix OTP Code",
            "text": f"""Hi {name},
Your OTP for TicketFlix registration is: {otp}
This OTP is valid for 5 minutes. Do not share it with anyone.
— TicketFlix Team"""
        })
        print(f"OTP sent to {email}: {otp}")
    except Exception as e:
        print(f"Email error: {str(e)}")

def send_otp_email(email: str, otp: str, name: str) -> bool:
    thread = threading.Thread(target=_send_email_task, args=(email, otp, name))
    thread.daemon = True
    thread.start()
    return True