import os, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER  = os.getenv("PUSHOVER_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SENDER_EMAIL   = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "bhoogs24@gmail.com")

# Test Pushover
resp = requests.post("https://api.pushover.net/1/messages.json", data={
    "token": PUSHOVER_TOKEN, "user": PUSHOVER_USER,
    "title": "Sale Alert", "message": "TEST: Travis Matthew 35% off sitewide | Code: SUMMER35 | Ends Sunday"
})
print(f"Pushover: {resp.status_code} {resp.text}")

# Test email
msg = MIMEMultipart("alternative")
msg["Subject"] = "TEST: Sale Alert — Travis Matthew"
msg["From"] = SENDER_EMAIL
msg["To"] = RECIPIENT_EMAIL
msg.attach(MIMEText("""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="color:#1a73e8;">Sale Alert</h2>
  <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0;">
    <div style="font-size:20px;font-weight:bold;color:#1a73e8;">Travis Matthew</div>
    <div style="font-size:16px;color:#2e7d32;font-weight:bold;margin-top:4px;">35% off sitewide this weekend</div>
    <div style="margin-top:6px;font-size:13px;">Code: <code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;">SUMMER35</code></div>
    <div style="color:#888;font-size:12px;margin-top:4px;">Ends: Sunday July 6</div>
    <div style="margin-top:12px;">
      <a href="https://www.travismathew.com" style="background:#1a73e8;color:white;padding:8px 16px;border-radius:4px;text-decoration:none;font-size:13px;">Shop Now →</a>
    </div>
  </div>
</body></html>
""", "html"))
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
    smtp.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
print("Email sent")
