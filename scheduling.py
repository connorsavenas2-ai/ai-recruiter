"""
Full scheduling automation — Jenny handles everything after a candidate qualifies:
1. Sends Calendly link immediately
2. Follows up if they don't book (Day 1, Day 3)
3. Sends 24-hour reminder (email + SMS)
4. Sends 1-hour reminder (SMS)
5. Detects no-shows and follows up automatically
6. Handles cancellations with instant rebook offer

Runs as a background scheduler alongside the webhook server.
"""

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import airtable_ats as ats
import email_outreach as email_out
from config import CALENDLY_BOOKING_LINK, YOUR_NAME, COMPANY_NAME

try:
    from sms_outreach import send_sms
    SMS_AVAILABLE = bool(os.getenv("TWILIO_ACCOUNT_SID"))
except:
    SMS_AVAILABLE = False
    def send_sms(phone, msg): print(f"[SMS DISABLED] → {phone}: {msg[:60]}")

try:
    from jenny.notifications import notify_interview_booked
except:
    def notify_interview_booked(*a, **kw): pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(dt_str.replace("Z", "+00:00"), fmt.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except:
            pass
    return None


# ── SEND CALENDLY LINK ────────────────────────────────────────────────────────

def get_booking_link(record_id: str = "") -> str:
    """
    Returns the best available booking link:
    1. Built-in booking page (uses Google Calendar, fully free)
    2. Calendly link (if configured)
    3. Email fallback
    """
    webhook_base = os.getenv("WEBHOOK_BASE_URL", "")
    if record_id and webhook_base:
        return f"{webhook_base}/book/{record_id}"
    if CALENDLY_BOOKING_LINK:
        return CALENDLY_BOOKING_LINK
    return f"mailto:{os.getenv('YOUR_EMAIL', '')}"


def send_calendly_to_qualified(record_id: str, name: str, email: str,
                               phone: str, job_title: str):
    """Send booking link immediately when candidate qualifies."""
    link = get_booking_link(record_id)

    # Email
    from email_outreach import _send
    first = name.split()[0]
    subject = f"You're moving forward! Book your interview — {job_title}"
    html = f"""
<p>Hi {first},</p>
<p>Great news — after reviewing your application for the <strong>{job_title}</strong> role
at {COMPANY_NAME}, we'd love to move you to a final interview with <strong>{os.getenv('YOUR_NAME','the hiring manager')}</strong>!</p>
<p>It's a quick 30-minute video call. Pick a time that works for you:</p>
<p style="text-align:center;margin:24px 0">
  <a href="{link}" style="background:#2563eb;color:white;padding:13px 28px;
     border-radius:8px;font-weight:700;font-size:15px;text-decoration:none;display:inline-block">
    Book My Interview →
  </a>
</p>
<p style="font-size:12px;color:#94a3b8">Or copy this link: {link}</p>
<p>Looking forward to speaking with you!</p>
<p>Jenny | {COMPANY_NAME}</p>"""
    _send(email, subject, html)

    # SMS
    if SMS_AVAILABLE and phone:
        msg = (f"Hi {first}! 🎉 Jenny from {COMPANY_NAME} — "
               f"you've been selected to interview for {job_title}! "
               f"Book your 30-min slot here: {link}")
        send_sms(phone, msg)

    # Mark in Airtable
    ats.update_candidate(record_id, {"Status": "Qualified"})
    print(f"[SCHEDULE] Sent booking link to {name}: {link}")


# ── BOOKING FOLLOW-UPS ────────────────────────────────────────────────────────

def check_unbooked_qualified():
    """
    Runs daily. Finds qualified candidates who haven't booked yet.
    Sends follow-up nudges at Day +1 and Day +3.
    """
    import requests as req
    from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    resp = req.get(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}",
        headers=headers,
        params={"filterByFormula": "AND({Status}='Qualified', {Calendly_Booked}=FALSE())"}
    )
    records = resp.json().get("records", [])
    now = _now_utc()

    for r in records:
        f         = r.get("fields", {})
        name      = f.get("Name", "")
        email     = f.get("Email", "")
        phone     = f.get("Phone", "")
        job       = f.get("Job_Title", "")
        called_dt = _parse_dt(f.get("Called_Date") or f.get("Applied_Date", ""))
        if not called_dt:
            continue

        days_since = (now - called_dt.replace(tzinfo=timezone.utc) if called_dt.tzinfo is None
                      else now - called_dt).days

        if days_since == 1:
            # Day 1 follow-up
            subject = f"Did you get a chance to book your interview? — {job}"
            html = (f"<p>Hi {name.split()[0]},</p>"
                    f"<p>Jenny here from {COMPANY_NAME}! Just wanted to make sure you got "
                    f"the booking link for your {job} interview. Here it is again:</p>"
                    f"<p><a href='{CALENDLY_BOOKING_LINK}'>Book Your Interview →</a></p>"
                    f"<p>Takes less than a minute to pick a time. Looking forward to it!</p>"
                    f"<p>Jenny | {COMPANY_NAME}</p>")
            email_out._send(email, subject, html)
            if SMS_AVAILABLE and phone:
                send_sms(phone, f"Hi {name.split()[0]}, Jenny from {COMPANY_NAME}! "
                                f"Don't miss your interview slot for {job}. "
                                f"Book here: {CALENDLY_BOOKING_LINK}")
            print(f"[SCHEDULE] Day-1 follow-up sent to {name}")

        elif days_since == 3:
            # Day 3 final nudge
            subject = f"Last chance to book — {job} at {COMPANY_NAME}"
            html = (f"<p>Hi {name.split()[0]},</p>"
                    f"<p>This is a final follow-up from Jenny at {COMPANY_NAME} "
                    f"about the {job} opportunity.</p>"
                    f"<p>We're filling this role quickly. If you're still interested, "
                    f"grab a time here: <a href='{CALENDLY_BOOKING_LINK}'>{CALENDLY_BOOKING_LINK}</a></p>"
                    f"<p>No worries if the timing isn't right — just let me know and "
                    f"we'll keep you in mind for future roles.</p>"
                    f"<p>Jenny | {COMPANY_NAME}</p>")
            email_out._send(email, subject, html)
            if SMS_AVAILABLE and phone:
                send_sms(phone, f"Final follow-up from Jenny ({COMPANY_NAME}) — "
                                f"still interested in {job}? Book here: {CALENDLY_BOOKING_LINK} "
                                f"or reply NO to opt out.")
            print(f"[SCHEDULE] Day-3 final nudge sent to {name}")


# ── INTERVIEW REMINDERS ───────────────────────────────────────────────────────

def send_interview_reminders():
    """
    Runs every 30 minutes. Finds booked interviews and sends:
    - 24-hour reminder (email + SMS)
    - 1-hour reminder (SMS only)
    """
    try:
        from calendly_integration import get_upcoming_interviews
        interviews = get_upcoming_interviews()
    except:
        return

    now = _now_utc()

    for interview in interviews:
        name      = interview.get("candidate_name", "")
        email     = interview.get("candidate_email", "")
        start_str = interview.get("start_time", "")
        join_url  = interview.get("join_url", "")
        start_dt  = _parse_dt(start_str)

        if not start_dt or not email:
            continue

        mins_until = (start_dt - now).total_seconds() / 60

        # 24-hour reminder window: 23.5h to 24.5h before
        if 23.5 * 60 <= mins_until <= 24.5 * 60:
            _send_24h_reminder(name, email, start_str, join_url)
            cand = ats.get_candidate_by_email(email)
            phone = cand["fields"].get("Phone", "") if cand else ""
            if SMS_AVAILABLE and phone:
                formatted = _format_datetime(start_dt)
                send_sms(phone,
                    f"Hi {name.split()[0]}! Reminder from Jenny — your interview with "
                    f"{YOUR_NAME} is tomorrow at {formatted}. "
                    + (f"Zoom link: {join_url}" if join_url else "Check your calendar for details."))

        # 1-hour reminder window: 55 to 65 minutes before
        elif 55 <= mins_until <= 65:
            cand = ats.get_candidate_by_email(email)
            phone = cand["fields"].get("Phone", "") if cand else ""
            if SMS_AVAILABLE and phone:
                send_sms(phone,
                    f"Hi {name.split()[0]}, your interview with {YOUR_NAME} starts in 1 hour! "
                    + (f"Join here: {join_url}" if join_url else "Check your calendar for the link."))
            print(f"[SCHEDULE] 1-hour reminder sent to {name}")


def _send_24h_reminder(name: str, email: str, start_str: str, join_url: str):
    from config import CALENDLY_BOOKING_LINK
    formatted = _format_datetime(_parse_dt(start_str))
    subject   = f"Your interview tomorrow — {formatted}"
    zoom_line = f'<p><strong>Join link:</strong> <a href="{join_url}">{join_url}</a></p>' if join_url else ""
    html = f"""
<p>Hi {name.split()[0]},</p>
<p>This is a friendly reminder from Jenny at {COMPANY_NAME} — your final interview
with <strong>{YOUR_NAME}</strong> is scheduled for tomorrow:</p>
<p style="background:#f0f9ff;border-left:4px solid #2563eb;padding:14px 18px;border-radius:6px">
  <strong>📅 {formatted}</strong><br>
  Duration: 30 minutes
</p>
{zoom_line}
<p><strong>Tips to prepare:</strong></p>
<ul>
  <li>Find a quiet spot with good lighting</li>
  <li>Have your resume or portfolio handy</li>
  <li>Prepare 2-3 questions for {YOUR_NAME}</li>
  <li>Log in 2-3 minutes early</li>
</ul>
<p>Need to reschedule? No problem — use this link:
<a href="{CALENDLY_BOOKING_LINK}">{CALENDLY_BOOKING_LINK}</a></p>
<p>Good luck — we're rooting for you! 🙌</p>
<p>Jenny | {COMPANY_NAME}</p>"""
    email_out._send(email, subject, html)
    print(f"[SCHEDULE] 24-hour reminder sent to {name}")


# ── NO-SHOW DETECTION ─────────────────────────────────────────────────────────

def check_no_shows():
    """
    Runs hourly. Finds interviews that ended 30-90 mins ago.
    If candidate is still in 'Final_Round' (not moved to Hired/Rejected),
    sends a no-show follow-up.
    """
    try:
        from calendly_integration import get_upcoming_interviews
        from calendly_integration import get_scheduled_events
    except:
        return

    import requests as req
    from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

    try:
        resp = req.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}",
            headers=headers,
            params={"filterByFormula": "{Status}='Final_Round'"}
        )
        candidates = resp.json().get("records", [])
    except:
        return

    now = _now_utc()

    for r in candidates:
        f            = r.get("fields", {})
        final_date_s = f.get("Final_Interview_Date", "")
        if not final_date_s:
            continue

        final_dt = _parse_dt(final_date_s + "T12:00:00+00:00") if "T" not in final_date_s else _parse_dt(final_date_s)
        if not final_dt:
            continue

        mins_ago = (now - final_dt).total_seconds() / 60

        # 45–90 mins after scheduled interview — likely a no-show
        if 45 <= mins_ago <= 90:
            name  = f.get("Name", "")
            email = f.get("Email", "")
            phone = f.get("Phone", "")
            job   = f.get("Job_Title", "")

            subject = f"We missed you today — {job} interview"
            html = (f"<p>Hi {name.split()[0]},</p>"
                    f"<p>We had your interview for the {job} role scheduled today but "
                    f"we weren't able to connect. No worries at all — things come up!</p>"
                    f"<p>Would you like to reschedule? Pick a new time here:<br>"
                    f"<a href='{CALENDLY_BOOKING_LINK}'>{CALENDLY_BOOKING_LINK}</a></p>"
                    f"<p>If you're no longer interested, no need to respond — "
                    f"we'll update your status accordingly.</p>"
                    f"<p>Jenny | {COMPANY_NAME}</p>")
            try:
                email_out._send(email, subject, html)
                if SMS_AVAILABLE and phone:
                    send_sms(phone, f"Hi {name.split()[0]}, Jenny from {COMPANY_NAME}. "
                                    f"Missed you at today's interview! Want to reschedule? "
                                    f"{CALENDLY_BOOKING_LINK}")
                print(f"[SCHEDULE] No-show follow-up sent to {name}")
                # Mark as needing follow-up
                ats.update_candidate(r["id"], {"Notes": (f.get("Notes","") + "\n\n[AUTO] No-show detected — follow-up sent.").strip()})
            except Exception as ex:
                print(f"[SCHEDULE] No-show email error: {ex}")


# ── CANCELLATION HANDLER ──────────────────────────────────────────────────────

def handle_cancellation(candidate_name: str, candidate_email: str,
                         job_title: str, phone: str = ""):
    """Call this from the Calendly webhook when invitee.canceled fires."""
    subject = f"Let's find a new time — {job_title}"
    html = (f"<p>Hi {candidate_name.split()[0]},</p>"
            f"<p>No worries about canceling! Life happens. 😊</p>"
            f"<p>Whenever you're ready, here's the link to pick a new time:<br>"
            f"<a href='{CALENDLY_BOOKING_LINK}'>{CALENDLY_BOOKING_LINK}</a></p>"
            f"<p>Jenny | {COMPANY_NAME}</p>")
    try:
        email_out._send(candidate_email, subject, html)
        if SMS_AVAILABLE and phone:
            send_sms(phone, f"Hi {candidate_name.split()[0]}, no worries! "
                           f"Rebook anytime: {CALENDLY_BOOKING_LINK}")
        print(f"[SCHEDULE] Cancellation rebook sent to {candidate_name}")
    except Exception as ex:
        print(f"[SCHEDULE] Cancellation handler error: {ex}")


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _format_datetime(dt: datetime | None) -> str:
    if not dt:
        return "your scheduled time"
    try:
        from datetime import timezone as tz
        eastern = dt.astimezone(timezone(timedelta(hours=-4)))  # ET (rough)
        return eastern.strftime("%A, %B %-d at %-I:%M %p ET")
    except:
        return str(dt)[:16]


# ── SCHEDULER STARTUP ─────────────────────────────────────────────────────────

_scheduler = None

def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Check unbooked qualified candidates — 9 AM daily
    _scheduler.add_job(check_unbooked_qualified, CronTrigger(hour=9, minute=0),
                       id="booking_followups", name="Booking follow-ups")

    # Send interview reminders — every 30 minutes
    _scheduler.add_job(send_interview_reminders, "interval", minutes=30,
                       id="reminders", name="Interview reminders")

    # Check for no-shows — every hour
    _scheduler.add_job(check_no_shows, "interval", hours=1,
                       id="noshows", name="No-show detection")

    _scheduler.start()
    print("[SCHEDULER] Started: booking follow-ups, reminders, no-show detection")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
