from __future__ import annotations

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# GOOGLE CALENDAR SETUP â€” Do this once before going live
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#
# 1. Go to https://console.cloud.google.com/
# 2. Create a new project (or use existing)
# 3. Enable the "Google Calendar API" for the project
# 4. Go to IAM & Admin -> Service Accounts -> Create Service Account
# 5. Give it a name, click Create and Continue
# 6. On the Keys tab, click Add Key -> JSON -> save the file
# 7. Place the JSON file at: credentials/google_service_account.json
#    (add credentials/ to .gitignore - never commit this file)
# 8. Open Google Calendar in your browser
# 9. Go to the calendar you want to use -> Settings -> Share with people
import logging
import os
import sys
import uuid
import pytz
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google.oauth2 import service_account

SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "credentials/google_service_account.json",
)
DELEGATED_CALENDAR_USER = os.getenv("GOOGLE_CALENDAR_DELEGATED_USER")

if not DELEGATED_CALENDAR_USER:
    raise RuntimeError("GOOGLE_CALENDAR_DELEGATED_USER is required")

CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
TIMEZONE_STR = os.getenv("MEETING_TIMEZONE", "Asia/Kolkata")
DURATION_MINUTES = int(os.getenv("MEETING_DURATION_MINUTES", "45"))
LOOKAHEAD_DAYS = int(os.getenv("MEETING_LOOKAHEAD_DAYS", "5"))
HOURS_START = int(os.getenv("MEETING_HOURS_START", "10"))
HOURS_END = int(os.getenv("MEETING_HOURS_END", "18"))
MOCK_MODE = os.getenv("GOOGLE_CALENDAR_MOCK", "true").lower() == "true"
MEETING_HOST_EMAIL = os.getenv("MEETING_HOST_EMAIL", DELEGATED_CALENDAR_USER)
BOOKED_SLOT_IDS: set[str] = set()
FIXED_TIME_SLOTS = (
    (9,  45),
    (10, 30),
    (11, 15),
    (13, 40),
    (14, 25),
    (15, 10),
    (15, 55),
    (16, 40),
    (17, 25),
)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_timezone():
    return pytz.timezone(TIMEZONE_STR)


def _build_label(slot_start: datetime) -> str:
    time_part = slot_start.strftime("%I:%M %p").lstrip("0")
    return f"{slot_start.strftime('%A')}, {slot_start.day} {slot_start.strftime('%b')} â€” {time_part}"


def _format_slot_label(slot_id: str) -> str:
    timezone = _get_timezone()
    slot_start = timezone.localize(datetime.strptime(slot_id, "%Y-%m-%d-%H-%M"))
    return _build_label(slot_start)


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _slot_to_dict(slot_start: datetime) -> dict[str, str]:
    slot_end = slot_start + timedelta(minutes=DURATION_MINUTES)
    return {
        "slot_id": slot_start.strftime("%Y-%m-%d-%H-%M"),
        "label": slot_start.strftime("%I:%M %p").lstrip("0"),
        "start_iso": slot_start.isoformat(),
        "end_iso": slot_end.isoformat(),
    }


def get_available_dates() -> list[dict[str, object]]:
    timezone = _get_timezone()
    today = datetime.now(timezone).date()
    dates: list[dict[str, object]] = []
    current_day = today + timedelta(days=1)

    while len(dates) < 5:
        if current_day.weekday() not in (5, 6):
            date_display = current_day.strftime("%d-%m-%Y")
            day_label = f"{current_day.strftime('%A')} â€” {date_display}"
            day_offset = (current_day - today).days
            if day_offset == 1:
                label = f"Tomorrow â€” {date_display}"
            elif day_offset == 2:
                label = f"This {current_day.strftime('%A')} â€” {date_display}"
            else:
                label = f"{current_day.strftime('%A')} â€” {date_display}"

            dates.append(
                {
                    "date_id": current_day.isoformat(),
                    "label": label,
                    "day_label": day_label,
                    "date_obj": current_day,
                }
            )
        current_day += timedelta(days=1)

    return dates


def _generate_mock_times(date_id: str) -> list[dict[str, str]]:
    timezone = _get_timezone()
    target_date = datetime.strptime(date_id, "%Y-%m-%d").date()
    now = datetime.now(timezone)
    times: list[dict[str, str]] = []

    for hour, minute in FIXED_TIME_SLOTS:
        slot_start = timezone.localize(
            datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                0,
            )
        )
        if target_date == now.date() and slot_start <= now:
            continue
        times.append(_slot_to_dict(slot_start))
        if len(times) >= 10:
            break

    return times


def get_available_times(date_id: str) -> list[dict[str, str]]:
    mock_times = [slot for slot in _generate_mock_times(date_id) if slot["slot_id"] not in BOOKED_SLOT_IDS]

    if MOCK_MODE:
        return mock_times[:10]

    timezone = _get_timezone()
    target_date = datetime.strptime(date_id, "%Y-%m-%d").date()
    day_start = timezone.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    day_end = day_start + timedelta(days=1)

    try:
        service = get_calendar_service()
        busy_response = (
            service.freebusy()
            .query(
                body={
                    "timeMin": day_start.isoformat(),
                    "timeMax": day_end.isoformat(),
                    "timeZone": TIMEZONE_STR,
                    "items": [{"id": CALENDAR_ID}],
                }
            )
            .execute()
        )
        busy_periods = busy_response.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])
        free_times: list[dict[str, str]] = []

        for slot in mock_times:
            if slot["slot_id"] in BOOKED_SLOT_IDS:
                continue
            slot_start = datetime.fromisoformat(slot["start_iso"])
            slot_end = datetime.fromisoformat(slot["end_iso"])
            overlaps_busy = False

            for busy in busy_periods:
                busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00")).astimezone(
                    timezone
                )
                busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00")).astimezone(
                    timezone
                )
                if slot_start < busy_end and slot_end > busy_start:
                    overlaps_busy = True
                    break

            if not overlaps_busy:
                free_times.append(slot)
            if len(free_times) >= 10:
                break

        return free_times
    except Exception as exc:
        _safe_print(f"[CalendarService] Warning: failed to query Google Calendar times for {date_id}: {exc}")
        return mock_times[:10]


def _annotate_slots(slots: list[dict[str, str]], source: str) -> list[dict[str, str]]:
    annotated_slots: list[dict[str, str]] = []
    for slot in slots:
        annotated_slot = dict(slot)
        annotated_slot["source"] = source
        annotated_slots.append(annotated_slot)
    return annotated_slots


def _generate_candidate_slots(days_ahead: int) -> list[dict[str, str]]:
    timezone = _get_timezone()
    now = datetime.now(timezone)
    first_day = (now + timedelta(days=1)).date()
    slots: list[dict[str, str]] = []

    for day_offset in range(days_ahead):
        current_day = first_day + timedelta(days=day_offset)
        day_start = timezone.localize(
            datetime(
                current_day.year,
                current_day.month,
                current_day.day,
                HOURS_START,
                0,
                0,
            )
        )

        if day_start.weekday() in (5, 6):
            continue

        for hour in range(HOURS_START, HOURS_END):
            slot_start = day_start.replace(hour=hour)
            slots.append(_slot_to_dict(slot_start))
            if len(slots) >= 8:
                return slots

    return slots


def _generate_mock_slots(days_ahead: int) -> list[dict[str, str]]:
    timezone = _get_timezone()
    start_day = (datetime.now(timezone) + timedelta(days=1)).date()
    allowed_hours = (10, 12, 14, 16)
    target_days = max(1, int(days_ahead))
    business_days = []
    slots: list[dict[str, str]] = []
    current_day = start_day

    while len(business_days) < target_days:
        if current_day.weekday() not in (5, 6):
            business_days.append(current_day)
        current_day += timedelta(days=1)

    for index, business_day in enumerate(business_days):
        remaining_slots = 8 - len(slots)
        remaining_days = len(business_days) - index
        slots_for_day = min(3, max(1, (remaining_slots + remaining_days - 1) // remaining_days))

        for hour in allowed_hours[:slots_for_day]:
            slot_start = timezone.localize(
                datetime(
                    business_day.year,
                    business_day.month,
                    business_day.day,
                    hour,
                    0,
                    0,
                )
            )
            slots.append(_slot_to_dict(slot_start))
            if len(slots) >= 8:
                return slots

    while len(slots) < 8:
        if current_day.weekday() in (5, 6):
            current_day += timedelta(days=1)
            continue

        for hour in allowed_hours[:3]:
            slot_start = timezone.localize(
                datetime(
                    current_day.year,
                    current_day.month,
                    current_day.day,
                    hour,
                    0,
                    0,
                )
            )
            slots.append(_slot_to_dict(slot_start))
            if len(slots) >= 8:
                return slots

        current_day += timedelta(days=1)

    return slots


def get_calendar_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError("Google service account file not found: " + SERVICE_ACCOUNT_FILE)
    logging.info("Using service account file: " + SERVICE_ACCOUNT_FILE)
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"],
    )
    delegated_credentials = credentials.with_subject(DELEGATED_CALENDAR_USER)
    logging.info("Successfully created delegated credentials for user: " + DELEGATED_CALENDAR_USER)
    return build("calendar", "v3", credentials=delegated_credentials)


def get_available_slots(days_ahead=None):
    effective_days = int(days_ahead or LOOKAHEAD_DAYS)

    if MOCK_MODE:
        available_slots = [
            slot for slot in _generate_mock_slots(effective_days) if slot["slot_id"] not in BOOKED_SLOT_IDS
        ]
        return _annotate_slots(available_slots, "mock_config")

    candidate_slots = _generate_candidate_slots(effective_days)

    try:
        service = get_calendar_service()
        if not candidate_slots:
            return []

        busy_response = (
            service.freebusy()
            .query(
                body={
                    "timeMin": candidate_slots[0]["start_iso"],
                    "timeMax": candidate_slots[-1]["end_iso"],
                    "timeZone": TIMEZONE_STR,
                    "items": [{"id": CALENDAR_ID}],
                }
            )
            .execute()
        )
        busy_periods = busy_response.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])

        free_slots: list[dict[str, str]] = []
        for slot in candidate_slots:
            if slot["slot_id"] in BOOKED_SLOT_IDS:
                continue
            slot_start = datetime.fromisoformat(slot["start_iso"])
            slot_end = datetime.fromisoformat(slot["end_iso"])
            overlaps_busy = False

            for busy in busy_periods:
                busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00")).astimezone(
                    _get_timezone()
                )
                busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00")).astimezone(
                    _get_timezone()
                )
                if slot_start < busy_end and slot_end > busy_start:
                    overlaps_busy = True
                    break

            if not overlaps_busy:
                free_slots.append(slot)
            if len(free_slots) >= 8:
                break

        return _annotate_slots(free_slots, "google_calendar")
    except Exception as exc:
        print("[CalendarService] Warning: failed to query Google Calendar; returning generated fallback slots:", exc)
        filtered_candidates = [slot for slot in candidate_slots if slot["slot_id"] not in BOOKED_SLOT_IDS]
        return _annotate_slots(filtered_candidates[:8], "fallback_generated")


def book_slot(
    slot_id=None,
    lead_name=None,
    lead_email=None,
    description="",
    *,
    user_name=None,
    user_email=None,
    meeting_purpose=None,
    preferred_time=None,
    host_email=None,
):
    slot_id = preferred_time or slot_id
    lead_name = user_name or lead_name
    lead_email = user_email or lead_email
    description = meeting_purpose or description
    effective_host_email = host_email or MEETING_HOST_EMAIL

    if not slot_id:
        raise ValueError("slot_id is required")
    timezone = _get_timezone()
    start_time = timezone.localize(datetime.strptime(slot_id, "%Y-%m-%d-%H-%M"))
    end_time = start_time + timedelta(minutes=DURATION_MINUTES)
    slot_label = _format_slot_label(slot_id)
    start_iso = start_time.isoformat()
    end_iso = end_time.isoformat()

    if slot_id in BOOKED_SLOT_IDS:
        return {
            "success": False,
            "error": "slot_already_booked",
            "slot_label": slot_label,
            "start_iso": start_iso,
            "end_iso": end_iso,
        }

    if MOCK_MODE:
        print(f"[CalendarService MOCK] Booked slot: {slot_id} for {lead_email}")
        BOOKED_SLOT_IDS.add(slot_id)
        return {
            "success": True,
            "event_id": "mock-event-" + slot_id,
            "meet_link": None,
            "slot_label": slot_label,
            "start_iso": start_iso,
            "end_iso": end_iso,
        }

    try:
        logging.info("aaaaa")
        service = get_calendar_service()
        logging.info("service=%s", service)  # Debugging line to check if service was created successfully
        logging.info("bbbbb")
        busy_check = (
            service.freebusy()
            .query(
                body={
                    "timeMin": start_iso,
                    "timeMax": end_iso,
                    "timeZone": TIMEZONE_STR,
                    "items": [{"id": CALENDAR_ID}],
                }
            )
            .execute()
        )
        logging.info("dddd")
        busy_periods = busy_check.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])
        if busy_periods:
            return {
                "success": False,
                "error": "slot_unavailable",
                "slot_label": slot_label,
                "start_iso": start_iso,
                "end_iso": end_iso,
            }

        attendee_emails: list[str] = []
        for candidate in (lead_email, effective_host_email):
            normalized = (candidate or "").strip().lower()
            if normalized and normalized not in attendee_emails:
                attendee_emails.append(normalized)

        attendees = [{"email": email} for email in attendee_emails]
        logging.info("Attendees for the event: %s", attendees)
        event_body = {
            "summary": "Strategy Call â€” " + (lead_name or "Valued Lead") + " x Ilmora Studios",
            "description": description or "Meeting booked via Vidio AI assistant",
            "start": {"dateTime": start_iso, "timeZone": TIMEZONE_STR},
            "end": {"dateTime": end_iso, "timeZone": TIMEZONE_STR},
            "attendees": attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": f"vidio-{uuid.uuid4().hex}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 1440},
                    {"method": "popup", "minutes": 30},
                ],
            },
            "extendedProperties": {
                "private": {
                    "source": "vidio_ai_calendar_booking",
                    "host_email": effective_host_email or "",
                    "delegated_user": DELEGATED_CALENDAR_USER,
                }
            },
        }
        logging.info("Calendar id=%s", CALENDAR_ID)
        created_event = (
            service.events()
            .insert(
                calendarId=CALENDAR_ID,
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )
        logging.info("cccc")
        meet_link = None
        conference_data = created_event.get("conferenceData", {})
        for entry in conference_data.get("entryPoints", []):
            if entry.get("uri"):
                meet_link = entry["uri"]
                break

        BOOKED_SLOT_IDS.add(slot_id)
        return {
            "success": True,
            "event_id": created_event.get("id", ""),
            "meet_link": meet_link,
            "slot_label": slot_label,
            "start_iso": start_iso,
            "end_iso": end_iso,
        }
    except Exception as exc:
        _safe_print(f"[CalendarService] Google API failed: {exc}")
        _safe_print("[CalendarService] âš ï¸ Event not created in Google Calendar.")
        _safe_print("[CalendarService] Booking failed; slot remains unbooked.")
        return {
            "success": False,
            "error": "calendar_booking_failed",
            "event_id": "",
            "meet_link": None,
            "slot_label": _format_slot_label(slot_id),
            "start_iso": start_iso,
            "end_iso": end_iso,
        }


def format_slots_for_chat(slots):
    lines = ["Here are some available slots for a strategy call:\n"]
    for index, slot in enumerate(slots, start=1):
        lines.append(f"{index}. {slot['label']}")
    lines.append(
        "\nReply with the number of your preferred slot (e.g. **1**, **2**, **3**), or type the date and time directly. Say **'more'** if none of these work and I'll find other options."
    )
    return "\n".join(lines)


def format_dates_for_chat(dates) -> str:
    lines = ["Please select a date for your strategy call:\n"]
    for index, date_item in enumerate(dates, start=1):
        lines.append(f"{index}. {date_item['label']}")
    lines.append("\nReply with a number to choose your date.")
    return "\n".join(lines)


def format_times_for_chat(times, date_label) -> str:
    import json

    return "TIMESLOTS::" + date_label + "::" + json.dumps([time_item["label"] for time_item in times])
