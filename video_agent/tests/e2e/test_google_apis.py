import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import datetime
import base64
from email.message import EmailMessage

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes needed for Calendar and Gmail API read/write
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://mail.google.com/'
]

# Service account file or OAuth client secrets file
SERVICE_ACCOUNT_FILE = 'credentials/google_service_account.json'
OAUTH_CREDENTIALS_FILE = 'credentials.json'

def get_credentials():
    """
    Attempts to load Google credentials.
    First tries to load a service account JSON.
    If not found, tries an OAuth2 user credentials flow.
    """
    creds = None
    
    # 1. Service Account
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"Loading Service Account from: {SERVICE_ACCOUNT_FILE}")
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return creds
        
    # 2. OAuth2 Client Secrets
    elif os.path.exists(OAUTH_CREDENTIALS_FILE):
        print(f"Loading OAuth flow using: {OAUTH_CREDENTIALS_FILE}")
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    OAUTH_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds
        
    else:
        print(f"Could not find '{SERVICE_ACCOUNT_FILE}' or '{OAUTH_CREDENTIALS_FILE}'.")
        print("Please ensure credentials are available before running the script.")
        return None

def test_calendar(creds, calendar_id='primary'):
    print("\n" + "="*40)
    print("--- Testing Google Calendar API ---")
    print("="*40)
    
    read_success = False
    write_success = False
    
    try:
        service = build('calendar', 'v3', credentials=creds)

        # 1. Read: Fetch next 5 events
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # UTC time format
        print(f"1) Fetching the upcoming 5 events from calendar: '{calendar_id}'...")
        events_result = service.events().list(
            calendarId=calendar_id, timeMin=now,
            maxResults=5, singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            print('   -> No upcoming events found.')
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"   -> {start} : {event['summary']}")
        
        read_success = True
        
        # 2. Write: Create test event
        print("\n2) Creating 'API Test Event'...")
        start_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        end_time = start_time + datetime.timedelta(hours=1)
        
        event_body = {
            'summary': 'API Test Event',
            'description': 'This is a test event created by the API verification script.',
            'start': {
                'dateTime': start_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
        }
        
        created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        print(f"   -> Event created successfully! Link: {created_event.get('htmlLink')}")
        write_success = True

    except HttpError as error:
        print(f"\n[!] HTTP Error in Calendar API: {error.resp.status} - {error.reason}")
        if error.resp.status == 403:
            print("    -> Permission Error (403): Ensure the Calendar API is enabled and your service account has calendar access.")
        elif error.resp.status == 404:
            print(f"    -> Not Found (404): The calendar '{calendar_id}' could not be found.")
            
    except Exception as e:
        print(f"\n[!] Unexpected Error in Calendar API: {e}")
        
    print("\n✅ Calendar Read: SUCCESS" if read_success else "\n❌ Calendar Read: FAILED")
    print("✅ Calendar Write: SUCCESS" if write_success else "❌ Calendar Write: FAILED")


def test_gmail(creds, send_test_email_to=None):
    print("\n" + "="*40)
    print("--- Testing Gmail API ---")
    print("="*40)
    
    read_success = False
    send_success = False
    
    try:
        service = build('gmail', 'v1', credentials=creds)

        # 1. Read: Fetch latest 5 emails
        print("1) Fetching the latest 5 emails from Inbox...")
        results = service.users().messages().list(userId='me', maxResults=5).execute()
        messages = results.get('messages', [])

        if not messages:
            print('   -> No messages found in Inbox.')
        else:
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id']).execute()
                headers = msg['payload'].get('headers', [])
                
                subject = next((header['value'] for header in headers if header['name'] == 'Subject'), 'No Subject')
                sender = next((header['value'] for header in headers if header['name'] == 'From'), 'Unknown Sender')
                print(f"   -> From: {sender} | Subject: {subject}")
                
        read_success = True

        # 2. Write: Send test email
        if send_test_email_to:
            print(f"\n2) Sending test email to: {send_test_email_to}...")
            message = EmailMessage()
            message.set_content('This is a test email sent from the Google API verification script.')
            message['To'] = send_test_email_to
            message['From'] = 'me'
            message['Subject'] = 'Google API Test Email'

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            send_message = service.users().messages().send(userId="me", body=create_message).execute()
            print(f"   -> Message Id: {send_message['id']} sent successfully.")
            send_success = True
        else:
            print("\n2) Skipping email send test. Provide 'send_test_email_to' argument to test sending.")
            send_success = True  # Assuming success since skipping doesn't mean failure

    except HttpError as error:
        print(f"\n[!] HTTP Error in Gmail API: {error.resp.status} - {error.reason}")
        if error.resp.status == 403:
            print("    -> Permission Error (403): Ensure Gmail API is enabled.")
            print("       If using a Service Account, it usually cannot read/write Gmail unless Domain-Wide Delegation is configured.")
        elif error.resp.status == 400:
            print("    -> Bad Request (400): Ensure 'userId' is valid (often 'me' doesn't work for Service Accounts without delegation).")
            
    except Exception as e:
        print(f"\n[!] Unexpected Error in Gmail API: {e}")

    print("\n✅ Gmail Read: SUCCESS" if read_success else "\n❌ Gmail Read: FAILED")
    print("✅ Gmail Send: SUCCESS" if send_success else "❌ Gmail Send: FAILED")


def main():
    print("Initializing Google API Diagnostics Script...\n")
    try:
        creds = get_credentials()
        if not creds:
            return

        # 1. Run Calendar Tests
        # You can change 'primary' to an exact calendar ID if the service account does not own a primary calendar
        test_calendar(creds, calendar_id="primary")
        
        # 2. Run Gmail Tests
        # Note: If using a Service Account without Domain Wide Delegation, "me" will refer to the headless SA and might fail for Gmail
        # Provide an email to test sending, e.g. "you@example.com"
        test_email_target = None  
        test_gmail(creds, send_test_email_to=test_email_target)
        
    except Exception as e:
        print(f"Setup/Auth Error: {e}")

if __name__ == '__main__':
    main()
