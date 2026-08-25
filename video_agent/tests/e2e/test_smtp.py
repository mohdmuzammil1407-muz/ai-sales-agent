import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test email from Vidio agent")
msg['Subject'] = "SMTP Test"
msg['From'] = "muzammil@ilmoraai.com"
msg['To'] = "muzammil@ilmoraai.com"

try:
    print("Connecting to SMTP server...")
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.set_debuglevel(1)  # To show verbose output of the connection
    server.starttls()
    print("Logging in...")
    # Used the password from the .env file
    server.login("muzammil@ilmoraai.com", "eabayptalvamshrf")
    
    print("Sending message...")
    server.send_message(msg)
    server.quit()
    print("\nEmail sent successfully!")
except Exception as e:
    print(f"\nFailed to send email: {e}")
