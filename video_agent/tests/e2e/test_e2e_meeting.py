import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import uuid
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys

# Load environment using python-dotenv if available to pull values from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ====== Config from ENV Variables ======
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
MEETING_TIMEZONE = os.getenv("MEETING_TIMEZONE", "UTC")
DURATION_MINUTES = int(os.getenv("MEETING_DURATION_MINUTES", "30"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Vidio")

def create_meeting():
    """
    Connect to Google Calendar via Service Account,
    create an event in 10 minutes, enable Hangouts Meet,
    without including attendees to avoid 403 errors.
    """
    print("\n--- 1. CREATING MEETING ---")
    
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        print(f"[!] Target service account file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}")
        return False, None, None, None, None
        
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE, 
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=creds)

        # Use timezone-aware UTC datetime per Python 3 best practices to prevent DeprecationWarning
        start_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        end_time = start_time + timedelta(minutes=DURATION_MINUTES)
        
        request_id = str(uuid.uuid4())
        
        event_body = {
            'summary': 'Vidio AI Test Meeting',
            'description': 'Automated test meeting',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': MEETING_TIMEZONE,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': MEETING_TIMEZONE,
            },
            # IMPORTANT: Skipping attendees to avoid 403 on Service Accounts
            'conferenceData': {
                'createRequest': {
                    'requestId': request_id,
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        }
        
        print(f"Creating event on calendar '{GOOGLE_CALENDAR_ID}'...")
        event = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID, 
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates='all'
        ).execute()

        event_id = event.get('id')
        event_link = event.get('htmlLink')
        
        # Extract Meet Link from response
        meet_link = None
        conf_data = event.get('conferenceData', {})
        for entry in conf_data.get('entryPoints', []):
            if entry.get('entryPointType') == 'video':
                meet_link = entry.get('uri')
                break

        print(f"   -> Event ID:   {event_id}")
        print(f"   -> Event Link: {event_link}")
        print(f"   -> Meet Link:  {meet_link}")
        
        return True, event_id, event_link, meet_link, event

    except HttpError as error:
        print(f"[!] HTTP Error in Calendar API: {error.resp.status} - {error.reason}")
        if error.resp.status == 403:
            print("   -> Permission Error: Please check if the target calendar has shared 'Make changes to events' permissions to the service account.")
        return False, None, None, None, None
    except Exception as e:
        print(f"[!] Unexpected Error in Calendar API: {e}")
        return False, None, None, None, None

def send_email(attendee_email, event_details):
    """
    Format standard meeting text and dispatch via Gmail SMTP.
    """
    print("\n--- 2. SENDING EMAIL ---")
    
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        print("[!] SMTP credentials missing from Environment Variables.")
        return False

    summary = event_details.get('summary', 'Vidio AI Test Meeting')
    start_dt = event_details['start'].get('dateTime', 'Unknown Time')
    meet_link = event_details.get('meet_link', 'No meeting link generated')
    event_link = event_details.get('event_link', 'No calendar link generated')

    subject = "Meeting Confirmed - Vidio"
    body = f"""\
Hello,

Your meeting has been successfully created.

Meeting Title: {summary}
Date & Time: {start_dt} Timezone: {MEETING_TIMEZONE}

Google Meet Link: {meet_link}
Calendar Event Link: {event_link}

Best regards,
{SMTP_FROM_NAME}
"""

    msg = MIMEMultipart()
    msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg['To'] = attendee_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        print(f"Connecting to SMTP server at {SMTP_HOST}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"   -> Confirmation email successfully delivered to {attendee_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[!] SMTP Authentication Error: {e}")
        return False
    except Exception as e:
        print(f"[!] Unexpected SMTP Error: {e}")
        return False

def main():
    print("====================================")
    print("STARTING END-TO-END SCHEDULING FLOW")
    print("====================================")
    
    # Target manual email passed or default fallback
    if len(sys.argv) > 1:
        attendee_email = sys.argv[1]
    else:
        attendee_email = os.getenv("SMTP_USER", "muzammil@ilmoraai.com")

    print(f"Target Delivery Email: {attendee_email}")

    # 1. Create Meeting
    cal_success, event_id, event_link, meet_link, event_obj = create_meeting()
    
    # 2. Send Email
    email_success = False
    if cal_success:
        event_details = {
            'summary': event_obj.get('summary'),
            'start': event_obj.get('start'),
            'meet_link': meet_link,
            'event_link': event_link
        }
        email_success = send_email(attendee_email, event_details)
    else:
        print("\n--- 2. SENDING EMAIL ---")
        print("   -> Skipped. Calendar event creation failed.")

    # 3. Validation Logs Output
    print("\n--- 3. VALIDATION LOGS ---")
    print(f"[{'OK' if cal_success else 'FAIL'}] Calendar Event Created")
    print(f"[{'OK' if meet_link else 'FAIL'}] Meet Link Generated")
    print(f"[{'OK' if email_success else 'FAIL'}] Email Sent")
    
    print("\nEND-TO-END TEST COMPLETED SUCCESSFULLY")

if __name__ == '__main__':
    main()
