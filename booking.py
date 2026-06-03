"""
Built-in booking system — 100% free, no Calendly needed.
Uses Google Calendar directly to show real availability and book slots.

Candidates visit: /book/<record_id>
  → See available times from Connor's Google Calendar
  → Pick a slot
  → Event created automatically
  → Confirmation email + SMS sent
"""

import os
from datetime import datetime, timedelta, timezone, date
from config import YOUR_NAME, COMPANY_NAME, CALENDLY_BOOKING_LINK


def get_available_slots(days_ahead: int = 10, slot_minutes: int = 30) -> list[dict]:
    """
    Returns available interview slots from Google Calendar.
    Falls back to a static schedule if Google Calendar isn't configured.
    """
    try:
        from google_calendar import get_available_slots as _gcal_slots
        slots = _gcal_slots(days_ahead=days_ahead, slot_duration_min=slot_minutes)
        return slots[:20]  # cap at 20 options
    except Exception as e:
        print(f"[BOOKING] Google Calendar unavailable ({e}), using static schedule")
        return _static_slots(days_ahead)


def _static_slots(days_ahead: int = 10) -> list[dict]:
    """Fallback: generate slots Mon-Fri 9am-4pm ET when Google Calendar is unavailable."""
    slots  = []
    now    = datetime.now(timezone.utc)
    # ET offset (EST = UTC-5, EDT = UTC-4; use -4 as approximation)
    et_offset = timedelta(hours=-4)

    for day_offset in range(1, days_ahead + 1):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:          # skip weekends
            continue
        for hour in [9, 10, 11, 13, 14, 15, 16]:
            slot_et  = (now + timedelta(days=day_offset)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            slot_utc = slot_et - et_offset   # convert ET → UTC
            end_utc  = slot_utc + timedelta(minutes=30)
            slots.append({
                "start":   slot_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end":     end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "display": slot_et.strftime("%A, %B %-d at %-I:%M %p ET")
            })
    return slots[:20]


def book_slot(
    start_time: str,
    end_time: str,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    record_id: str = ""
) -> dict:
    """
    Creates a Google Calendar event and returns the event + Zoom/Meet link.
    Falls back to email-only confirmation if Google Calendar isn't configured.
    """
    zoom_link = ""
    event_id  = ""

    try:
        from google_calendar import create_interview_event
        event = create_interview_event(
            candidate_name  = candidate_name,
            candidate_email = candidate_email,
            job_title       = job_title,
            start_time      = start_time,
            end_time        = end_time
        )
        event_id  = event.get("id", "")
        # Google Meet link auto-created when conferenceData is requested
        conf_data = event.get("conferenceData", {})
        for ep in conf_data.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                zoom_link = ep.get("uri", "")
                break
    except Exception as e:
        print(f"[BOOKING] Calendar event creation failed: {e}")

    # Parse display time
    try:
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        et = dt - timedelta(hours=4)
        display_time = et.strftime("%A, %B %-d at %-I:%M %p ET")
    except:
        display_time = start_time

    # Send confirmation emails
    try:
        from email_outreach import send_interview_confirmation, _send
        from config import YOUR_EMAIL
        # Candidate confirmation
        send_interview_confirmation(
            candidate_name, candidate_email, job_title, display_time, zoom_link
        )
        # Notify Connor
        _send(
            YOUR_EMAIL,
            f"📅 Interview booked — {candidate_name} ({job_title})",
            f"<p><strong>{candidate_name}</strong> booked a final interview for "
            f"<strong>{job_title}</strong> on <strong>{display_time}</strong>.<br>"
            + (f"Google Meet: <a href='{zoom_link}'>{zoom_link}</a>" if zoom_link else "Check your Google Calendar.")
            + "</p>"
        )
    except Exception as e:
        print(f"[BOOKING] Confirmation email failed: {e}")

    # Update Airtable
    if record_id:
        try:
            import airtable_ats as ats
            ats.mark_calendly_booked(record_id, start_time[:10])
        except:
            pass

    # Discord/Slack notification
    try:
        from jenny.notifications import notify_interview_booked
        notify_interview_booked(candidate_name, job_title, display_time)
    except:
        pass

    # SMS reminder schedule (send immediately as confirmation)
    try:
        from sms_outreach import send_sms
        from config import TWILIO_ACCOUNT_SID
        if TWILIO_ACCOUNT_SID:
            import airtable_ats as ats
            cand = ats.get_candidate_by_email(candidate_email)
            phone = cand["fields"].get("Phone", "") if cand else ""
            if phone:
                send_sms(phone,
                    f"Confirmed! Your interview with {YOUR_NAME} is booked for {display_time}. "
                    + (f"Google Meet: {zoom_link}" if zoom_link else "Check your email for details.")
                )
    except:
        pass

    return {
        "ok":           True,
        "event_id":     event_id,
        "display_time": display_time,
        "zoom_link":    zoom_link
    }
