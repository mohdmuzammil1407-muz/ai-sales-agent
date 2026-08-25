from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MEETING_HOST_EMAIL = os.getenv("MEETING_HOST_EMAIL") or os.getenv("SMTP_FROM_EMAIL") or SMTP_USER
MEETING_HOST_NAME = (
    os.getenv("MEETING_HOST_NAME")
    or os.getenv("SMTP_FROM_NAME")
    or "Ilmora Studios"
)
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))


def get_smtp_status() -> dict[str, object]:
    configured = bool(SMTP_HOST and (SMTP_USER or MEETING_HOST_EMAIL))
    return {
        "configured": configured,
        "host": SMTP_HOST or None,
        "port": SMTP_PORT,
        "from_email": MEETING_HOST_EMAIL or None,
        "from_name": MEETING_HOST_NAME,
        "use_tls": True,
        "has_credentials": bool(SMTP_USER and SMTP_PASSWORD),
        "timeout_seconds": 15,
    }


def _build_message(to_email: str, subject: str, body: str) -> MIMEMultipart:
    message = MIMEMultipart()
    message["From"] = f"{MEETING_HOST_NAME} <{MEETING_HOST_EMAIL or SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))
    return message


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _send_email(to_email: str, subject: str, body: str) -> dict[str, object]:
    smtp_status = get_smtp_status()
    if not to_email:
        return {
            "success": False,
            "delivery": "skipped",
            "message": "Recipient email is missing.",
            "smtp": smtp_status,
        }

    if not SMTP_USER or not SMTP_PASSWORD:
        _safe_print("[EmailService MOCK] Would send confirmation to: " + to_email)
        _safe_print(body)
        return {
            "success": True,
            "delivery": "mock",
            "smtp": smtp_status,
        }

    try:
        message = _build_message(to_email, subject, body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(message["From"], [to_email], message.as_string())
        return {
            "success": True,
            "delivery": "email",
            "smtp": smtp_status,
        }
    except Exception as exc:
        print("[EmailService] SMTP error:", exc)
        return {
            "success": False,
            "delivery": "failed",
            "message": str(exc),
            "smtp": smtp_status,
        }


def send_meeting_confirmation(lead_name, lead_email, slot_label, meet_link):
    lead_display_name = lead_name or "there"
    duration_minutes = os.getenv("MEETING_DURATION_MINUTES", "30")
    lead_link_line = f"\n🔗 Join call: {meet_link}" if meet_link else ""
    host_link_line = f"\nLink: {meet_link}" if meet_link else ""

    lead_body = (
        f"Hi {lead_display_name},\n\n"
        "Your strategy call with Ilmora Studios has been confirmed!\n\n"
        f"📅 {slot_label}\n"
        f"⏱  {duration_minutes} minutes"
        f"{lead_link_line}\n\n"
        "We'll use this time to understand your project, walk you through\n"
        "our packages, and figure out the best fit for your brand.\n\n"
        "See you then!\n"
        "— Ilmora Studios Team\n"
        "studios@ilmoraai.com | @ilmora.studios"
    )

    host_body = (
        "New meeting booked via Vidio AI.\n\n"
        f"Lead: {lead_name or 'Valued Lead'}\n"
        f"Email: {lead_email or 'Not provided'}\n"
        f"Slot: {slot_label}"
        f"{host_link_line}"
    )

    try:
        lead_result = {
            "success": False,
            "delivery": "skipped",
        }
        if lead_email:
            lead_result = _send_email(
                lead_email,
                "Your strategy call with Ilmora Studios is confirmed 🎬",
                lead_body,
            )
        else:
            _safe_print("[EmailService MOCK] Would send confirmation to: " + str(lead_email))
            _safe_print(lead_body)

        host_result = _send_email(
            MEETING_HOST_EMAIL or SMTP_USER,
            f"New strategy call booked — {lead_name or 'Valued Lead'}",
            host_body,
        )
        return {
            "success": bool(lead_result.get("success") and host_result.get("success")),
            "lead_delivery": lead_result.get("delivery", "unknown"),
            "host_delivery": host_result.get("delivery", "unknown"),
            "lead_result": lead_result,
            "host_result": host_result,
        }
    except Exception as exc:
        print("[EmailService] Failed to send meeting confirmation:", exc)
        return {
            "success": False,
            "lead_delivery": "failed",
            "host_delivery": "failed",
            "error": str(exc),
        }


def send_meeting_reminder(lead_name: str, lead_email: str, slot_label: str, meet_link: str | None) -> dict[str, object]:
    lead_display_name = lead_name or "there"
    link_line = f"\n🔗 Join call: {meet_link}" if meet_link else ""
    body = (
        f"Hi {lead_display_name},\n\n"
        "Quick reminder: your strategy call with Ilmora Studios starts in 30 minutes.\n\n"
        f"📅 {slot_label}"
        f"{link_line}\n\n"
        "Please be ready a few minutes early so we can begin on time.\n\n"
        "— Ilmora Studios Team\n"
        "studios@ilmoraai.com | @ilmora.studios"
    )
    return _send_email(
        lead_email,
        "Reminder: Your Ilmora strategy call starts in 30 minutes",
        body,
    )


def send_otp_email(*, to_email: str, otp_code: str, name: str | None = None) -> dict[str, object]:
    greeting_name = name or "there"
    body = (
        f"Hello {greeting_name},\n\n"
        f"Your Vidio verification code is: {otp_code}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes.\n\n"
        "If you did not request this code, you can ignore this email.\n"
    )
    return _send_email(to_email, "Your Vidio verification code", body)


def send_test_email(*, to_email: str, subject: str | None = None) -> dict[str, object]:
    body = (
        "This is a Vidio SMTP test email.\n\n"
        "If you received this message, SMTP delivery is working."
    )
    return _send_email(to_email, subject or "Vidio SMTP test", body)


def send_order_notification_email(name: str | None, email: str | None, whatsapp: str, package: str | None, order_ref: str) -> dict[str, object]:
    subject = f"🎬 New Order Intent — {order_ref}"
    body = f"""New order received via Vidio chatbot!
    
Reference: {order_ref}
Name:      {name or 'N/A'}
Email:     {email or 'N/A'}
WhatsApp:  {whatsapp}
Package:   {package or 'N/A'}
    
Action required: Send payment link to {whatsapp} within 2 hours.
"""
    return _send_email(
        to_email=os.getenv('ADMIN_EMAIL') or MEETING_HOST_EMAIL or SMTP_USER,
        subject=subject,
        body=body
    )
