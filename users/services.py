import random
import threading
import smtplib
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


def send_email_oauth2(to_email, subject, body, html_body=None):
    access_token = get_access_token()

    # Correct XOAUTH2 format
    auth_string = f"user=mayureshsonawane1526@gmail.com\x01auth=Bearer {access_token}\x01\x01"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = 'TicketFlix <mayureshsonawane1526@gmail.com>'
    msg['To'] = to_email
    msg.attach(MIMEText(body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.docmd('AUTH', f'XOAUTH2 {auth_b64}')
        server.sendmail('mayureshsonawane1526@gmail.com', to_email, msg.as_string())

def _send_email_task(email: str, otp: str, name: str):
    try:
        send_email_oauth2(
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