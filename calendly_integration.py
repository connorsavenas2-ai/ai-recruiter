"""
Calendly integration — fetches scheduled events, handles webhooks,
syncs bookings to Airtable and Google Calendar.
"""

import requests
from config import CALENDLY_API_KEY, CALENDLY_USER_URI, WEBHOOK_BASE_URL

BASE_URL = "https://api.calendly.com"
HEADERS  = {
    "Authorization": f"Bearer {CALENDLY_API_KEY}",
    "Content-Type": "application/json"
}


def get_scheduled_events(count: int = 20) -> list:
    params = {
        "user": CALENDLY_USER_URI,
        "count": count,
        "status": "active",
        "sort": "start_time:asc"
    }
    resp = requests.get(f"{BASE_URL}/scheduled_events", headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("collection", [])


def get_event_invitees(event_uuid: str) -> list:
    resp = requests.get(f"{BASE_URL}/scheduled_events/{event_uuid}/invitees", headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("collection", [])


def get_upcoming_interviews() -> list:
    """Returns a clean list of upcoming booked interviews."""
    events = get_scheduled_events()
    interviews = []
    for event in events:
        uuid = event["uri"].split("/")[-1]
        invitees = get_event_invitees(uuid)
        for inv in invitees:
            interviews.append({
                "candidate_name":  inv.get("name", ""),
                "candidate_email": inv.get("email", ""),
                "event_name":      event.get("name", ""),
                "start_time":      event.get("start_time", ""),
                "end_time":        event.get("end_time", ""),
                "join_url":        event.get("location", {}).get("join_url", ""),
                "event_uuid":      uuid
            })
    return interviews


def create_webhook_subscription() -> dict:
    """
    Subscribe to Calendly webhooks so we're notified when someone books.
    Run this once during setup.
    """
    payload = {
        "url": f"{WEBHOOK_BASE_URL}/webhooks/calendly",
        "events": ["invitee.created", "invitee.canceled"],
        "user": CALENDLY_USER_URI,
        "scope": "user"
    }
    resp = requests.post(f"{BASE_URL}/webhook_subscriptions", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def list_webhook_subscriptions() -> list:
    params = {"user": CALENDLY_USER_URI, "scope": "user"}
    resp = requests.get(f"{BASE_URL}/webhook_subscriptions", headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("collection", [])
