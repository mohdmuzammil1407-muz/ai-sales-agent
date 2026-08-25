from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta

import pytz

from app.database.db import SessionLocal
from app.models.db_models import Conversation, Lead
from app.services.email_service import send_meeting_reminder

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_interval_seconds = int(os.getenv("MEETING_REMINDER_POLL_SECONDS", "60"))


def _get_timezone():
    return pytz.timezone(os.getenv("MEETING_TIMEZONE", "Asia/Kolkata"))


def _run_once() -> None:
    db = SessionLocal()
    try:
        conversations = db.query(Conversation).filter(Conversation.meeting_meta.isnot(None)).all()
        now = datetime.now(_get_timezone())

        for conversation in conversations:
            try:
                payload = json.loads(conversation.meeting_meta or "{}")
            except Exception:
                continue

            if not payload.get("meeting_booked"):
                continue
            if payload.get("meeting_reminder_sent"):
                continue

            slot_iso = payload.get("meeting_slot_start_iso")
            if not slot_iso:
                continue

            try:
                slot_start = datetime.fromisoformat(slot_iso)
            except Exception:
                continue

            if slot_start.tzinfo is None:
                slot_start = _get_timezone().localize(slot_start)

            reminder_at = slot_start - timedelta(minutes=30)
            if not (reminder_at <= now < slot_start):
                continue

            lead = (
                db.query(Lead)
                .filter(Lead.conversation_id == conversation.conversation_id)
                .order_by(Lead.updated_at.desc(), Lead.created_at.desc())
                .first()
            )
            lead_email = (lead.email if lead and lead.email else "").strip()
            lead_name = (lead.name if lead and lead.name else "") or "there"
            if not lead_email:
                continue

            reminder_result = send_meeting_reminder(
                lead_name=lead_name,
                lead_email=lead_email,
                slot_label=payload.get("meeting_slot_label") or "your scheduled strategy call",
                meet_link=None,
            )
            if reminder_result.get("success"):
                payload["meeting_reminder_sent"] = True
                conversation.meeting_meta = json.dumps(payload)
                logger.info(
                    "Meeting reminder sent for conversation %s to %s",
                    conversation.conversation_id,
                    lead_email,
                )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Meeting reminder loop error: %s", exc)
    finally:
        db.close()


def _worker_loop() -> None:
    while not _stop_event.is_set():
        _run_once()
        _stop_event.wait(_interval_seconds)


def start_meeting_reminder_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="meeting-reminder-worker",
        daemon=True,
    )
    _worker_thread.start()
    logger.info("Meeting reminder worker started.")


def stop_meeting_reminder_worker() -> None:
    global _worker_thread
    _stop_event.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=2)
    _worker_thread = None
    logger.info("Meeting reminder worker stopped.")
