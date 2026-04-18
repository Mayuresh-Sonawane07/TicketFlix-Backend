import random
import threading
import resend
import requests
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
        # Get fresh access token using refresh token
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": settings.GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        # Build RFC 2822 email message
        import base64
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["From"] = f"TicketFlix <{settings.GMAIL_CLIENT_EMAIL}>"
        msg["To"] = email
        msg["Subject"] = "Your TicketFlix OTP Code"
        msg.attach(MIMEText(f"Hi {name},\n\nYour OTP is: {otp}\n\nValid for 5 minutes.", "plain"))
        msg.attach(MIMEText(_build_otp_html(name, otp), "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        # Send via Gmail API
        send_response = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw},
            timeout=10,
        )
        send_response.raise_for_status()
        print(f"[EMAIL] OTP sent to {email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {e}")

def send_otp_email(email: str, otp: str, name: str) -> bool:
    thread = threading.Thread(target=_send_email_task, args=(email, otp, name))
    thread.daemon = True
    thread.start()
    return True



def send_email_oauth2(to_email: str, subject: str, body: str, html_body: str = None):
    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": "TicketFlix <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "text": body,
        "html": html_body or body,
    })