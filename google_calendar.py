"""
Google Calendar integration — checks availability, creates interview events.
"""

import os
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import GOOGLE_CREDS_FILE, GOOGLE_CALENDAR_ID

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "google_token.pickle"


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def get_busy_times(days_ahead: int = 7) -> list:
    """Returns list of busy time blocks for the next N days."""
    service = get_calendar_service()
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)

    body = {
        "timeMin": now.isoformat() + "Z",
        "timeMax": end.isoformat() + "Z",
        "items": [{"id": GOOGLE_CALENDAR_ID}]
    }
    result = service.freebusy().query(body=body).execute()
    return result.get("calendars", {}).get(GOOGLE_CALENDAR_ID, {}).get("busy", [])


def get_available_slots(days_ahead: int = 7, slot_duration_min: int = 30) -> list:
    """Returns list of available interview slots in business hours."""
    busy = get_busy_times(days_ahead)
    busy_ranges = [(b["start"], b["end"]) for b in busy]

    slots = []
    now = datetime.utcnow()
    for day_offset in range(1, days_ahead + 1):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:  # skip weekends
            continue
        for hour in [9, 10, 11, 13, 14, 15, 16]:
            slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end   = slot_start + timedelta(minutes=slot_duration_min)
            start_str  = slot_start.isoformat() + "Z"
            end_str    = slot_end.isoformat() + "Z"

            conflict = any(
                not (end_str <= b[0] or start_str >= b[1])
                for b in busy_ranges
            )
            if not conflict:
                slots.append({
                    "start": start_str,
                    "end": end_str,
                    "display": slot_start.strftime("%A %B %d at %I:%M %p ET")
                })
    return slots


def create_interview_event(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    start_time: str,
    end_time: str,
    zoom_link: str = "",
    notes: str = ""
) -> dict:
    service = get_calendar_service()

    description = f"Final round interview with {candidate_name} for {job_title}.\n\n"
    if notes:
        description += f"Recruiter notes:\n{notes}\n\n"
    if zoom_link:
        description += f"Zoom: {zoom_link}"

    event = {
        "summary": f"Final Interview – {candidate_name} ({job_title})",
        "description": description,
        "start": {"dateTime": start_time, "timeZone": "America/New_York"},
        "end":   {"dateTime": end_time,   "timeZone": "America/New_York"},
        "attendees": [{"email": candidate_email}],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 15}
            ]
        },
        "conferenceData": {
            "createRequest": {"requestId": f"ai-recruiter-{candidate_name.replace(' ', '-')}"}
        } if not zoom_link else {}
    }

    result = service.events().insert(
        calendarId=GOOGLE_CALENDAR_ID,
        body=event,
        conferenceDataVersion=1 if not zoom_link else 0,
        sendUpdates="all"
    ).execute()
    return result


def get_upcoming_interviews(days_ahead: int = 14) -> list:
    service = get_calendar_service()
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)
    result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=now.isoformat() + "Z",
        timeMax=end.isoformat() + "Z",
        q="Final Interview",
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return result.get("items", [])
