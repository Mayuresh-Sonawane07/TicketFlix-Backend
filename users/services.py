import random
import threading
import base64
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def get_access_token():
    res = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.GMAIL_CLIENT_ID,
        'client_secret': settings.GMAIL_CLIENT_SECRET,
        'refresh_token': settings.GMAIL_REFRESH_TOKEN,
        'grant_type': 'refresh_token',
    })
    return res.json().get('access_token')


def send_email_via_gmail_api(to_email, subject, body, html_body=None):
    access_token = get_access_token()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = 'TicketFlix <mayureshsonawane1526@gmail.com>'
    msg['To'] = to_email
    msg.attach(MIMEText(body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    response = requests.post(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={'raw': raw}
    )
    print(f"Gmail API response: {response.status_code} {response.text}")
    if response.status_code not in (200, 202):
        raise Exception(f"Gmail API error: {response.text}")


def _send_email_task(email: str, otp: str, name: str):
    try:
        send_email_via_gmail_api(
            to_email=email,
            subject="Your TicketFlix OTP Code",
            body=f"Hi {name},\n\nYour OTP is: {otp}\n\nValid for 5 minutes.\n— TicketFlix"
        )
        print(f"OTP sent to {email}: {otp}")
    except Exception as e:
        print(f"Email error: {str(e)}")


def send_otp_email(email: str, otp: str, name: str) -> bool:
    thread = threading.Thread(target=_send_email_task, args=(email, otp, name))
    thread.daemon = True
    thread.start()
    return True


# Keep this for bookings/views.py to import
send_email_oauth2 = send_email_via_gmail_api