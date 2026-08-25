# 🎥 Vidio Chatbot Backend

Welcome to the backend API component of the **Vidio Chatbot** — an intelligent, AI-powered sales agent and booking assistant built for **Ilmora Studios**. The system uses a FastAPI framework connected to Anthropic's Claude 3.5 Sonnet to drive conversational sales, handle objections, score leads, verify users via OTP, and book strategy sessions directly into Google Calendar.

---

## ✨ Key Features

- 🤖 **AI Sales Agent**: Claude 3.5 Sonnet (`claude-3-5-sonnet`) drives sales interactions, manages dynamic package recommendations, handles pricing objections, and directs users toward booking calls.
- 🔐 **OTP Verification**: Multi-channel authentication using email OTP (via SMTP) and SMS OTP (configured via Twilio).
- 📅 **Google Calendar DWD**: Automatic booking integration utilizing Google Calendar API with Domain-Wide Delegation (DWD) to book events on the Ilmora Studios-Meetings calendar with a unique Google Meet link.
- 🤝 **Deal Closing Flow**: Detects buying intent, prompts for a WhatsApp contact, generates a unique order reference (`#VID-XXXXXX`), and triggers instant email notifications to administrators.
- 📋 **Lead Management**: Automatically captures and logs lead records containing names, emails, phone numbers, WhatsApp contacts, recommended packages, order intent flags, and order references.
- 📧 **Email Notifications**: Handles email generation for OTP delivery, meeting confirmations (sent to both client and host), and admin order notifications.
- 🔑 **Admin JWT Auth**: Protects access to dashboard endpoints with JSON Web Tokens (JWT).
- 🌐 **Widget Serving**: Serves the static embeddable chat widget script (`widget.js`) at the `/widget/widget.js` endpoint.

---

## 🛠️ Directory Structure

```text
video_agent/
├── app/
│   ├── core/
│   │   ├── prompts.py          ← Claude system prompt + pricing catalog
│   │   └── state_manager.py    ← Session/flow state management
│   ├── database/
│   │   ├── db.py               ← SQLAlchemy engine + Base
│   │   └── init_db.py          ← DB init + safe ALTER TABLE migrations
│   ├── models/
│   │   ├── conversation.py     ← ConversationState Pydantic model
│   │   └── db_models.py        ← SQLAlchemy ORM models
│   ├── routes/
│   │   ├── chat.py             ← Main chat logic + all flow handlers
│   │   └── admin.py            ← Admin auth + JWT + dashboard data
│   ├── services/
│   │   ├── calendar_service.py ← Google Calendar DWD integration
│   │   ├── email_service.py    ← SMTP email (OTP, meeting, order)
│   │   ├── email_verifier.py   ← Disposable email blocklist
│   │   ├── intent_service.py   ← Intent + objection detection
│   │   ├── llm_service.py      ← Claude API calls
│   │   └── otp_service.py      ← OTP generation + verification
│   └── main.py                 ← FastAPI app entry + CORS
├── credentials/
│   └── google_service_account.json
├── widget/
│   └── widget.js               ← Source embeddable chat widget
├── Dockerfile
├── requirements.txt
└── .env
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the `video_agent` root directory using the following variables:

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres1@localhost:5432/vidio_agent` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | `sk-ant-...` |
| `ADMIN_EMAIL` | Admin login email address | `admin@ilmoraai.com` |
| `ADMIN_PASSWORD` | Admin login password | `securepassword` |
| `JWT_SECRET` | Secret key used for signing JWTs | `yoursecretkeyhere` |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `http://localhost:3000` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to Google Service Account Credentials | `credentials/google_service_account.json` |
| `GOOGLE_CALENDAR_DELEGATED_USER`| G-Suite user email for Calendar delegation | `muzammil@ilmoraai.com` |
| `CALENDAR_ID` | Google Calendar target ID | `primary` or group calendar ID |
| `MEETING_TIMEZONE` | Timezone context for available slots | `Asia/Kolkata` |
| `MEETING_HOST_EMAIL` | Target email address representing the host | `muzammil@ilmoraai.com` |
| `SLOT_START_HOUR` | Day shift start hour (24-hour clock) | `9` |
| `SLOT_END_HOUR` | Day shift end hour (24-hour clock) | `18` |
| `SLOT_DURATION` | Meeting block duration in minutes | `45` |
| `TWILIO_ACCOUNT_SID` | Account SID for Twilio SMS integration | `AC...` |
| `TWILIO_AUTH_TOKEN` | Auth Token for Twilio API | `your_auth_token` |
| `TWILIO_PHONE_NUMBER` | Outbound SMS Twilio phone number | `+1234567890` |
| `MOCK_OTP_MODE` | Bypass live OTP generation (sends 123456) | `false` |
| `OTP_EXPIRY_SECONDS` | Lifetime of a single generated OTP | `300` |
| `SMTP_HOST` | Host address of SMTP server | `smtp.gmail.com` |
| `SMTP_PORT` | Port of SMTP server | `587` |
| `SMTP_USER` | Authenticating SMTP username | `muzammil@ilmoraai.com` |
| `SMTP_PASS` | App password for SMTP auth | `your_app_password` |

---

## 🚀 Getting Started

### Local Setup

1. **Activate Environment & Install Dependencies**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Initialize Database**:
   ```bash
   python -c "from app.database.init_db import init_db; init_db()"
   ```

3. **Start Server**:
   ```bash
   python run.py
   # or
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

---

## 🐳 Docker Deployment

The backend can be built and run standalone using the provided `Dockerfile`:
```bash
docker build -t vidio-backend .
docker run -d -p 8000:8000 --env-file .env vidio-backend
```

---

## 📖 API Reference

### Chat & Client Services
* `POST /api/v1/chat` - Submits chat inputs to the Claude agent.
* `POST /api/v1/auth/request-otp` - Submits credentials to trigger an OTP via Email or SMS.
* `POST /api/v1/auth/verify-otp` - Validates the verification OTP token.
* `GET /widget/widget.js` - Serves the static embeddable script for website widget placement.

### Admin Dashboard (JWT Guarded)
* `POST /api/v1/admin/login` - Submits password to receive a JWT access token.
* `GET /api/v1/admin/leads` - Returns lists of captured customer leads.
* `GET /api/v1/admin/conversations` - Returns message transcripts and agent timelines.
* `GET /api/v1/admin/meetings` - Returns list of strategy call bookings.
