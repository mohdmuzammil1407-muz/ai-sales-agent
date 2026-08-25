import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


DELEGATED_USER = os.getenv(
    "GOOGLE_CALENDAR_DELEGATED_USER",
    "muzammil@ilmoraai.com",
)
SERVICE_ACCOUNT = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "credentials/google_service_account.json",
)
TEST_ATTENDEE = os.getenv(
    "TEST_ATTENDEE_EMAIL",
    "muzammil@ilmoraai.com",
)
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID") or os.getenv("CALENDAR_ID", "primary")
MEETING_TZ = os.getenv("MEETING_TIMEZONE", "Asia/Kolkata")

TEST_EVENT = {
    "summary": "[AUTO TEST] DWD Calendar Validation",
    "description": "Automated DWD integration test event. Safe to delete.",
    "attendee": TEST_ATTENDEE,
    "start": datetime.now(timezone.utc) + timedelta(days=2),
    "duration": 45,
}

report = {
    "timestamp": datetime.now().isoformat(),
    "delegated_user": DELEGATED_USER,
    "calendar_id": CALENDAR_ID,
    "tests": [],
    "passed": 0,
    "failed": 0,
    "warnings": [],
    "created_event_id": None,
}


def log_test(name, passed, detail="", warning=False):
    status = "PASS" if passed else "FAIL"
    entry = {
        "test": name,
        "status": status,
        "detail": detail,
        "warning": warning,
    }
    report["tests"].append(entry)
    if passed:
        report["passed"] += 1
    else:
        report["failed"] += 1
    if warning:
        report["warnings"].append(f"{name}: {detail}")
    marker = "OK" if passed else "X"
    print(f"  [{marker}] {name}")
    if detail:
        print(f"      {detail}")


class TestDWDCalendarIntegration(unittest.TestCase):
    def test_01_env_vars_present(self):
        print("\nTEST 1: Environment Variable Check")
        required_vars = {
            "GOOGLE_SERVICE_ACCOUNT_FILE": os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            "GOOGLE_CALENDAR_DELEGATED_USER": os.getenv("GOOGLE_CALENDAR_DELEGATED_USER"),
            "MEETING_HOST_EMAIL": os.getenv("MEETING_HOST_EMAIL"),
            "MEETING_TIMEZONE": os.getenv("MEETING_TIMEZONE"),
            "GOOGLE_CALENDAR_ID or CALENDAR_ID": CALENDAR_ID,
        }

        all_present = True
        for var, val in required_vars.items():
            present = bool(val and str(val).strip())
            safe_detail = str(val) if present else "NOT SET"
            log_test(f"ENV: {var}", present, safe_detail)
            if not present:
                all_present = False

        self.assertTrue(all_present, "One or more required env vars are missing")

    def test_02_service_account_file(self):
        print("\nTEST 2: Service Account File Validation")
        exists = os.path.exists(SERVICE_ACCOUNT)
        log_test("Service account file exists", exists, SERVICE_ACCOUNT)
        self.assertTrue(exists, f"File not found: {SERVICE_ACCOUNT}")

        with open(SERVICE_ACCOUNT, encoding="utf-8") as handle:
            sa_data = json.load(handle)
        log_test("Service account file is valid JSON", True)

        required_fields = [
            "type",
            "project_id",
            "private_key_id",
            "private_key",
            "client_email",
            "client_id",
            "token_uri",
        ]
        for field in required_fields:
            present = field in sa_data
            if field == "private_key":
                detail = "***redacted***" if present else "MISSING"
            elif field == "client_email":
                detail = sa_data.get(field, "MISSING")
            else:
                detail = "present" if present else "MISSING"
            log_test(f"SA field: {field}", present, detail)
            self.assertTrue(present, f"Missing field in SA file: {field}")

        correct_type = sa_data.get("type") == "service_account"
        log_test("SA type is service_account", correct_type, sa_data.get("type", "missing"))
        self.assertTrue(correct_type)

    def test_03_credentials_init(self):
        print("\nTEST 3: DWD Credential Initialization")
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/calendar"]
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT,
            scopes=scopes,
        )
        log_test(
            "Base service account credentials loaded",
            True,
            f"SA email: {creds.service_account_email}",
        )

        delegated = creds.with_subject(DELEGATED_USER)
        subject = getattr(delegated, "_subject", None)
        log_test(
            "DWD impersonation credentials created",
            bool(subject == DELEGATED_USER),
            f"Impersonating: {subject}",
        )
        self.assertEqual(subject, DELEGATED_USER)

    def test_04_calendar_service_build(self):
        print("\nTEST 4: Google Calendar Service Build")
        from app.services.calendar_service import get_calendar_service

        service = get_calendar_service()
        log_test(
            "get_calendar_service() returned service object",
            service is not None,
            str(type(service)),
        )
        self.assertIsNotNone(service)

    def test_05_calendar_api_auth(self):
        print("\nTEST 5: Live Calendar API Authentication")
        from app.services.calendar_service import get_calendar_service

        service = get_calendar_service()
        try:
            calendar_list = service.calendarList().list(maxResults=10).execute()
            accessible = len(calendar_list.get("items", []))
            log_test(
                "Calendar API authenticated successfully",
                True,
                f"Calendars accessible: {accessible}",
            )
        except Exception as exc:
            error_str = str(exc)
            if "invalid_grant" in error_str:
                detail = (
                    "DWD not authorized in Google Admin Console for "
                    "https://www.googleapis.com/auth/calendar"
                )
            elif "unauthorized_client" in error_str:
                detail = "Service account is not authorized for Domain-Wide Delegation"
            else:
                detail = error_str
            log_test("Calendar API auth", False, detail)
            raise

    def test_06_create_test_event(self):
        print("\nTEST 6: Create Test Calendar Event")
        from app.services.calendar_service import get_calendar_service

        service = get_calendar_service()

        start = TEST_EVENT["start"]
        end = start + timedelta(minutes=TEST_EVENT["duration"])
        event_body = {
            "summary": TEST_EVENT["summary"],
            "description": TEST_EVENT["description"],
            "start": {
                "dateTime": start.isoformat(),
                "timeZone": MEETING_TZ,
            },
            "end": {
                "dateTime": end.isoformat(),
                "timeZone": MEETING_TZ,
            },
            "attendees": [
                {"email": TEST_EVENT["attendee"]},
                {"email": DELEGATED_USER},
            ],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 1440},
                    {"method": "popup", "minutes": 30},
                ],
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": f"vidio-test-{int(datetime.now().timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        try:
            result = (
                service.events()
                .insert(
                    calendarId=CALENDAR_ID,
                    body=event_body,
                    conferenceDataVersion=1,
                    sendUpdates="all",
                )
                .execute()
            )
        except Exception as exc:
            log_test("Create test event", False, str(exc))
            raise

        event_id = result.get("id")
        event_link = result.get("htmlLink")
        meet_link = None
        for entry in result.get("conferenceData", {}).get("entryPoints", []):
            if entry.get("uri"):
                meet_link = entry["uri"]
                break

        report["created_event_id"] = event_id

        log_test(
            "Test event created in Google Calendar",
            bool(event_id),
            f"Event ID: {event_id or 'missing'}",
        )
        log_test(
            "Calendar event link generated",
            bool(event_link),
            event_link or "No link",
        )
        log_test(
            "Google Meet link generated",
            bool(meet_link),
            meet_link or "No Meet link returned",
            warning=not bool(meet_link),
        )

        attendee_count = len(result.get("attendees", []))
        log_test(
            "Attendees persisted on event",
            attendee_count >= 1,
            f"Attendee count on event: {attendee_count}",
        )
        log_test(
            "Attendee invite dispatch requested",
            True,
            "Event insert used sendUpdates='all'; mailbox delivery must be confirmed in Gmail UI",
            warning=True,
        )

        self.assertTrue(event_id, "No event ID returned")

    def test_07_verify_event_exists(self):
        print("\nTEST 7: Verify Event Exists on Delegated Calendar")
        if not report.get("created_event_id"):
            log_test("Event verification", False, "Skipped - no event ID from TEST 6")
            self.skipTest("No event created in TEST 6")

        from app.services.calendar_service import get_calendar_service

        service = get_calendar_service()
        fetched = (
            service.events()
            .get(
                calendarId=CALENDAR_ID,
                eventId=report["created_event_id"],
            )
            .execute()
        )

        log_test(
            "Event found on calendar",
            fetched.get("id") == report["created_event_id"],
            f"Summary: {fetched.get('summary', '')}",
        )
        log_test(
            "Event status is confirmed",
            fetched.get("status") == "confirmed",
            f"Status: {fetched.get('status')}",
        )

    def test_08_cleanup_test_event(self):
        print("\nTEST 8: Delete Test Event (Cleanup)")
        if not report.get("created_event_id"):
            log_test("Test event cleanup", False, "Skipped - no event to delete")
            self.skipTest("No event to clean up")

        from app.services.calendar_service import get_calendar_service

        service = get_calendar_service()
        try:
            (
                service.events()
                .delete(
                    calendarId=CALENDAR_ID,
                    eventId=report["created_event_id"],
                    sendUpdates="all",
                )
                .execute()
            )
            log_test(
                "Test event deleted successfully",
                True,
                f"Deleted: {report['created_event_id']}",
            )
        except Exception as exc:
            log_test("Test event cleanup", False, str(exc), warning=True)

    def test_09_error_handling(self):
        print("\nTEST 9: Error Handling")
        from google.oauth2 import service_account

        try:
            service_account.Credentials.from_service_account_file(
                "nonexistent_file_xyz.json",
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            log_test("Handles missing SA file", False, "Should have raised")
        except FileNotFoundError:
            log_test("Handles missing SA file", True, "FileNotFoundError raised correctly")
        except Exception as exc:
            log_test("Handles missing SA file", True, f"Raised {type(exc).__name__}")

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        delegated = creds.with_subject("")
        subject = getattr(delegated, "_subject", None)
        empty_subject_rejected = bool(subject)
        log_test(
            "Empty subject rejected by library",
            empty_subject_rejected,
            "with_subject('') returns an object with empty subject; app-level validation is required"
            if not empty_subject_rejected
            else f"Subject: {subject}",
            warning=not empty_subject_rejected,
        )


def generate_report():
    total = report["passed"] + report["failed"]
    pass_pct = (report["passed"] / total * 100) if total else 0

    if report["failed"] == 0:
        status = "ALL TESTS PASSED"
    elif report["failed"] < total:
        status = "SOME TESTS FAILED"
    else:
        status = "ALL TESTS FAILED"

    print("\n" + "=" * 60)
    print("VIDIO - DWD CALENDAR INTEGRATION VALIDATION REPORT")
    print("=" * 60)
    print(f"Timestamp      : {report['timestamp']}")
    print(f"Delegated User : {report['delegated_user']}")
    print(f"Calendar ID    : {report['calendar_id']}")
    print(f"Total Tests    : {total}")
    print(f"Passed         : {report['passed']} ({pass_pct:.0f}%)")
    print(f"Failed         : {report['failed']}")
    print(f"Overall Status : {status}")
    print("=" * 60)

    print("\nDETAILED RESULTS:\n")
    for item in report["tests"]:
        print(f"{item['status']}: {item['test']}")
        if item["detail"]:
            print(f"  {item['detail']}")

    if report["warnings"]:
        print("\nWARNINGS:")
        for warning in report["warnings"]:
            print(f"- {warning}")

    report_path = os.path.join("tests", "e2e", "dwd_validation_report.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    print(f"\nFull report saved to: {report_path}")
    print("=" * 60)

    return report["failed"] == 0


if __name__ == "__main__":
    print("\nStarting DWD Calendar Integration Tests...")
    print(f"Delegated User : {DELEGATED_USER}")
    print(f"Service Account: {SERVICE_ACCOUNT}\n")

    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite = loader.loadTestsFromTestCase(TestDWDCalendarIntegration)
    runner = unittest.TextTestRunner(verbosity=0, failfast=False)
    runner.run(suite)
    all_passed = generate_report()
    sys.exit(0 if all_passed else 1)
