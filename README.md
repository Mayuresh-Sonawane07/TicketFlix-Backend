# TicketFlix — Backend

> Django REST API for the TicketFlix online event booking platform.

**Live API:** https://web-production-cf420.up.railway.app/api  
**Frontend:** https://ticketflix-ten.vercel.app  
**Admin Panel:** https://web-production-cf420.up.railway.app/admin/

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 5.2 + Django REST Framework 3.16 |
| Database | PostgreSQL (Railway managed) |
| Server | Gunicorn (4 workers) |
| Auth | Custom JWT (base64) + Google OAuth2 |
| Email | Gmail API (OAuth2 HTTP) |
| Payments | Razorpay |
| Hosting | Railway |

---

## Project Structure

```
ticketflix/          # Core config — settings, urls, wsgi
users/               # Auth — registration, OTP, login, Google OAuth, profile
events/              # Events CRUD + reviews
theaters/            # Theater, screen, seat, show management
bookings/            # Booking lifecycle, QR verification, check-in
payments/            # Razorpay order creation + signature verification
```

---

## Features

- Email OTP registration and verification
- Google OAuth2 social login
- Role-based access control (Customer / Venue Owner / Admin)
- Real-time seat booking with atomic transaction concurrency control
- Tier-based seat pricing (Silver / Gold / Platinum)
- Razorpay payment integration with HMAC-SHA256 signature verification
- QR code generation (embedded in confirmation email + PDF ticket)
- QR ticket verification with check-in tracking (prevents duplicate entry)
- Booking cancellation with 24-hour rule
- Gmail API transactional emails (OTP, booking confirmation, cancellation)
- Venue owner analytics endpoint
- Django admin panel at `/admin/`
- Security: HSTS, CORS, CSRF, SSL redirect, XSS filter

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/users/send-otp/` | Public | Send registration OTP |
| POST | `/api/users/verify-otp/` | Public | Register with OTP |
| POST | `/api/users/login/` | Public | Email login |
| POST | `/api/users/google-login/` | Public | Google OAuth login |
| POST | `/api/users/forgot-password/` | Public | Send reset OTP |
| POST | `/api/users/reset-password/` | Public | Reset password |
| GET/PATCH | `/api/users/profile/` | Required | View/update profile |
| GET | `/api/events/` | Public | List events (search/filter) |
| GET | `/api/events/{id}/` | Public | Event detail + shows |
| POST | `/api/events/` | VENUE_OWNER | Create event |
| PATCH/DELETE | `/api/events/{id}/` | VENUE_OWNER | Update/delete event |
| POST | `/api/events/{id}/reviews/` | Customer | Submit review |
| GET/POST | `/api/theaters/theaters/` | VENUE_OWNER | List/create theaters |
| POST | `/api/theaters/screens/` | VENUE_OWNER | Add screen to theater |
| GET | `/api/theaters/shows/` | Public | List shows for event |
| POST | `/api/theaters/shows/` | VENUE_OWNER | Schedule show |
| GET | `/api/bookings/` | Required | My bookings |
| POST | `/api/bookings/{id}/cancel/` | Customer | Cancel booking |
| GET | `/api/bookings/{id}/verify/` | Public | Verify QR ticket |
| POST | `/api/bookings/{id}/verify/` | Public | Mark ticket as used |
| GET | `/api/bookings/venue_analytics/` | VENUE_OWNER | Booking analytics |
| POST | `/api/payments/create-order/` | Required | Create Razorpay order |
| POST | `/api/payments/verify/` | Required | Verify payment + create booking |

Full API documentation: [TicketFlix API Docs](https://github.com/Mayuresh-Sonawane07/TicketFlix-Backend)

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (or use SQLite for local dev)

### Steps

```bash
# Clone the repo
git clone https://github.com/Mayuresh-Sonawane07/TicketFlix-Backend.git
cd TicketFlix-Backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (create a .env file or export directly)
export SECRET_KEY=your-secret-key
export DEBUG=True
export DATABASE_URL=postgresql://user:password@localhost/ticketflix
export EMAIL_HOST_PASSWORD=your-gmail-app-password
export GMAIL_CLIENT_ID=your-google-client-id
export GMAIL_CLIENT_SECRET=your-google-client-secret
export GMAIL_REFRESH_TOKEN=your-refresh-token

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | True for dev, False for production |
| `DATABASE_URL` | PostgreSQL connection URL |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `EMAIL_HOST_PASSWORD` | Gmail app password (fallback SMTP) |
| `GMAIL_CLIENT_ID` | Google OAuth2 client ID |
| `GMAIL_CLIENT_SECRET` | Google OAuth2 client secret |
| `GMAIL_REFRESH_TOKEN` | Google OAuth2 refresh token |
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API secret |

---

## Deployment (Railway)

The backend auto-deploys from the `main` branch on Railway using the `Procfile`:

```
web: gunicorn ticketflix.wsgi:application --workers 4 --bind 0.0.0.0:$PORT --timeout 120
```

Railway auto-injects `DATABASE_URL` for the managed PostgreSQL instance. All other secrets are added as Railway environment variables.

---

## Database

PostgreSQL on Railway. To run migrations on the production database:

```bash
DATABASE_URL="postgresql://..." python manage.py migrate
```

To load fixture data:

```bash
DATABASE_URL="postgresql://..." python manage.py loaddata db_backup.json
```

---

## Authentication

All protected endpoints require:

```
Authorization: Basic <base64(email:password)>
```

Google OAuth users use:

```
Authorization: Basic <base64(email:google-oauth)>
```

---

## Team

| Name | Role |
|------|------|
| Mayuresh Sonawane | Team Lead & Full Stack Developer |
| Krish Shripat | Backend Developer |
| Rohitkumar Prajapati | Frontend Developer |
| Bhavya Varma | UI/UX & Testing |

**Guide:** Prof. Rujuta Chaudhari  
**Institution:** A.P. Shah Institute of Technology, Thane

---

## License

This project is developed for academic purposes at A.P. Shah Institute of Technology.
