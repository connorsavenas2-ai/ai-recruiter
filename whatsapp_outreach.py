"""
WhatsApp candidate outreach via OpenClaw's WhatsApp integration.
OpenClaw exposes a local API at port 18789 for messaging.

Usage:
  python whatsapp_outreach.py --phone +15551234567 --name "Jane" --job "Finance Analyst"
"""

import requests
import json
from config import get_ai_client, YOUR_NAME, COMPANY_NAME, CALENDLY_BOOKING_LINK

OPENCLAW_BASE = "http://localhost:18789"


def _send_whatsapp(phone: str, message: str) -> dict:
    """Send a WhatsApp message via OpenClaw gateway."""
    resp = requests.post(
        f"{OPENCLAW_BASE}/api/whatsapp/send",
        json={"phone": phone, "message": message},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def _build_outreach_message(candidate_name: str, job_title: str, job_description: str) -> str:
    client, model = get_ai_client()
    prompt = f"""Write a short WhatsApp message recruiting {candidate_name} for a {job_title} role.

From: {YOUR_NAME} at {COMPANY_NAME}
Job: {job_title}
Description: {job_description}
Type: 1099 contractor
Calendly: {CALENDLY_BOOKING_LINK}

Rules:
- WhatsApp tone: casual, short, direct
- Max 3 sentences + 1 CTA line
- Disclose it's a contract/1099 opportunity
- End with: "Interested? Book a quick call: {CALENDLY_BOOKING_LINK}"
- No emojis unless very subtle

Return ONLY the message text, no JSON, no quotes."""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.5
    )
    return resp.choices[0].message.content.strip()


def send_outreach(phone: str, candidate_name: str, job_title: str,
                  job_description: str = "") -> bool:
    msg = _build_outreach_message(candidate_name, job_title, job_description)
    try:
        _send_whatsapp(phone, msg)
        print(f"  [WA] Sent to {candidate_name} ({phone})")
        return True
    except Exception as e:
        print(f"  [WA ERROR] {phone}: {e}")
        return False


def send_calendly_link(phone: str, candidate_name: str, job_title: str) -> bool:
    msg = (
        f"Hi {candidate_name.split()[0]}! This is {YOUR_NAME} from {COMPANY_NAME}. "
        f"Great speaking with you about the {job_title} role. "
        f"Here's the link to book your next interview: {CALENDLY_BOOKING_LINK}"
    )
    try:
        _send_whatsapp(phone, msg)
        return True
    except Exception as e:
        print(f"  [WA ERROR] {e}")
        return False


def send_interview_reminder(phone: str, candidate_name: str, interview_time: str) -> bool:
    msg = (
        f"Hi {candidate_name.split()[0]}, just a reminder — your interview with {YOUR_NAME} "
        f"is {interview_time}. Reply CONFIRM or let me know if you need to reschedule."
    )
    try:
        _send_whatsapp(phone, msg)
        return True
    except Exception as e:
        print(f"  [WA ERROR] {e}")
        return False


def check_openclaw_status() -> bool:
    """Check if OpenClaw gateway is running."""
    try:
        resp = requests.get(f"{OPENCLAW_BASE}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    parser.add_argument("--name",  required=True)
    parser.add_argument("--job",   required=True)
    parser.add_argument("--desc",  default="")
    args = parser.parse_args()

    if not check_openclaw_status():
        print("OpenClaw gateway not running. Start OpenClaw first.")
        exit(1)

    send_outreach(args.phone, args.name, args.job, args.desc)
