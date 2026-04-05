import random
import threading
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def _build_otp_html(name: str, otp: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#0a0a0a;border-radius:12px;overflow:hidden;border:1px solid #222;">
      <div style="background:#dc2626;padding:24px 32px;">
        <h1 style="color:white;margin:0;font-size:22px;letter-spacing:1px;">🎬 TicketFlix</h1>
      </div>
      <div style="padding:32px;">
        <p style="color:#e5e5e5;font-size:16px;margin-top:0;">Hi <strong>{name}</strong>,</p>
        <p style="color:#9ca3af;font-size:14px;">Use the OTP below to verify your account. It expires in <strong style="color:#f87171;">5 minutes</strong>.</p>
        <div style="background:#1f1f1f;border:1px solid #333;border-radius:10px;padding:24px;text-align:center;margin:24px 0;">
          <p style="color:#9ca3af;font-size:12px;margin:0 0 8px;text-transform:uppercase;letter-spacing:2px;">Your OTP</p>
          <p style="color:#ffffff;font-size:40px;font-weight:bold;letter-spacing:10px;margin:0;">{otp}</p>
        </div>
        <p style="color:#6b7280;font-size:12px;">If you did not request this, you can safely ignore this email.</p>
      </div>
      <div style="background:#111;padding:16px 32px;border-top:1px solid #222;">
        <p style="color:#4b5563;font-size:11px;margin:0;text-align:center;">© 2025 TicketFlix. Do not share this OTP with anyone.</p>
      </div>
    </div>
    """


def _send_email_task(email: str, otp: str, name: str):
    try:
        subject = "Your TicketFlix OTP Code"
        text_body = f"Hi {name},\n\nYour OTP is: {otp}\n\nValid for 5 minutes. Do not share it.\n\n— TicketFlix"
        html_body = _build_otp_html(name, otp)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        print(f"[EMAIL] OTP sent to {email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {e}")


def send_otp_email(email: str, otp: str, name: str) -> bool:
    thread = threading.Thread(target=_send_email_task, args=(email, otp, name))
    thread.daemon = True
    thread.start()
    return True


# ── Alias kept so bookings/views.py import doesn't break ──────────────────────
def send_email_oauth2(to_email: str, subject: str, body: str, html_body: str = None):
    """
    Drop-in replacement for the old Gmail OAuth sender.
    Now uses Django's SMTP backend instead.
    """
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        raise