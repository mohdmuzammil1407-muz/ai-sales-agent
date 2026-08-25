import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# save as test_email.py and run: python test_email.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
load_dotenv()

msg = MIMEMultipart()
msg["From"]    = os.getenv("SMTP_USER")
msg["To"]      = os.getenv("SMTP_USER")  # send to yourself first
msg["Subject"] = "Test — Vidio Email Service"
msg.attach(MIMEText("Email service is working correctly.", "plain"))

with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
    server.starttls()
    server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    server.send_message(msg)
    print("✅ Email sent successfully")