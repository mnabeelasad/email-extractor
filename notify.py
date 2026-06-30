"""
notify.py
---------
Sends an email notification when conflicting values are detected.

When a new KWP email arrives with values that differ from what we already
have saved, the colleague needs to review manually. Instead of hoping they
scroll to the bottom of device_info.txt, we send them a direct email.

Settings from .env:
    SMTP_SERVER=smtp.strato.de
    SMTP_PORT=587
    SMTP_USER=nabeel.asad@wqs.de
    SMTP_PASSWORD=your-password
    NOTIFY_EMAIL=nabeel.asad@wqs.de   (who gets the notification)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_conflict_notification(
    client_name: str,
    conflicts: list[dict],
    source_label: str,
) -> bool:
    """
    Send an email notification about conflicting values.
    Returns True if sent successfully, False otherwise.
    """
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.strato.de")
    smtp_port   = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user   = os.environ.get("SMTP_USER") or os.environ.get("EMAIL_USER")
    smtp_pass   = os.environ.get("SMTP_PASSWORD") or os.environ.get("EMAIL_PASSWORD")
    notify_email = os.environ.get("NOTIFY_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("    ⚠ SMTP not configured — skipping conflict notification.")
        return False

    # build the email body
    conflict_lines = []
    for c in conflicts:
        conflict_lines.append(f"""
  Field         : {c.get('field', '')}
  Current value : {c.get('current_value', '')}
  New value     : {c.get('new_value', '')}
  {"─" * 40}""")

    body = f"""Hi,

The automated extraction system received a new email from client {client_name}
that contains values different from what is already saved.

Please review the following and update manually if the new value is correct:
{"".join(conflict_lines)}

Source email : {source_label}
Detected at  : {datetime.now().strftime("%Y-%m-%d %H:%M")}

The current values have NOT been changed automatically.
Please open data/{client_name}/device_info.txt to review and update.

— Automated KWP Extraction System
"""

    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = notify_email
    msg["Subject"] = f"⚠ {client_name} Device Data — {len(conflicts)} value(s) need review"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, notify_email, msg.as_string())
        print(f"    ✅ Conflict notification sent to {notify_email}")
        return True
    except Exception as e:
        print(f"    ⚠ Could not send notification: {e}")
        return False