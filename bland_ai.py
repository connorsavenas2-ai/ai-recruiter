"""
Bland.ai integration — handles all AI voice calls.
Outbound: screens candidates automatically.
Inbound: answers candidate calls 24/7.
"""

import requests
import json
from config import BLAND_API_KEY, BLAND_VOICE_ID, COMPANY_NAME, YOUR_NAME, CALENDLY_BOOKING_LINK, WEBHOOK_BASE_URL

BASE_URL = "https://api.bland.ai/v1"
HEADERS  = {"authorization": BLAND_API_KEY, "Content-Type": "application/json"}


def build_call_script(job_title: str, job_type: str = "1099", is_internship: bool = False) -> str:
    comp_type = "hourly contract rate" if not is_internship else "unpaid or stipend internship"
    return f"""
You are Alex, a professional AI recruiting assistant for {COMPANY_NAME}.
You are calling to conduct a brief first-round phone screen for a {job_title} position.

IMPORTANT RULES:
- Always introduce yourself as an AI assistant working on behalf of {YOUR_NAME} at {COMPANY_NAME}.
- Never claim to be human. If asked, confirm you are an AI.
- Be warm, conversational, and professional — like a friendly recruiter.
- Keep the call to 8-12 minutes max.
- This is a {job_type} position ({comp_type}).
- If the candidate is a strong fit (score 7+/10), offer to schedule a final interview with {YOUR_NAME} directly.
- Calendly booking link: {CALENDLY_BOOKING_LINK}

CONVERSATION FLOW:

1. INTRO (30 sec):
   "Hi, is this [candidate name]? Great! My name is Alex, I'm an AI recruiting assistant
   calling on behalf of {YOUR_NAME} at {COMPANY_NAME}. I'm reaching out about the {job_title}
   opportunity you applied for. Is now a good time for a quick 10-minute chat?"

2. ROLE CONFIRMATION (1 min):
   - Confirm they saw the job posting and are still interested
   - Give a 30-second overview of the role and company
   - Ask: "Does that sound like something you're interested in?"

3. EXPERIENCE SCREEN (3 min):
   - "Can you walk me through your most relevant experience for this role?"
   - "What specific skills do you bring to a {job_title} position?"
   - "Have you worked in a 1099 / independent contractor capacity before?"

4. AVAILABILITY & COMP (2 min):
   - "What's your availability to start?"
   - "What compensation range are you looking for in this role?"
   - "Are you currently interviewing elsewhere?"

5. MOTIVATION (1 min):
   - "What draws you to this particular opportunity?"
   - "What are you looking for in your next role?"

6. CANDIDATE QUESTIONS (1 min):
   - "Do you have any questions about the role or company?"

7. CLOSE — QUALIFIED (1 min):
   "Based on our conversation, I think there's a strong fit here. I'd love to connect you
   with {YOUR_NAME} directly for a final conversation. I'm going to send you a link right now
   to book a time that works for you. Check your texts/email in the next few minutes.
   Looking forward to the next step!"

7b. CLOSE — NOT QUALIFIED (30 sec):
   "Thank you so much for your time today. We'll review everything and be in touch
   if there's a strong match. Have a great day!"

OBJECTION HANDLING:
- "I'm not interested": "Totally understand! Is there a particular type of role that would
  be a better fit? I work across several positions."
- "What company is this?": Give full company name and explain the role briefly.
- "I don't talk to AI": "That's completely fair. I can have {YOUR_NAME} follow up
  with you directly by email instead — would that work?"
- "I'm not available right now": "No problem at all, when would be a better time?
  I can call back or send details by text."

Always be respectful if they want to end the call. Never be pushy.
"""


def trigger_outbound_call(
    phone_number: str,
    candidate_name: str,
    job_title: str,
    job_type: str = "1099",
    is_internship: bool = False,
    candidate_email: str = "",
    airtable_record_id: str = ""
) -> dict:
    """Trigger an outbound AI screening call to a candidate."""
    script = build_call_script(job_title, job_type, is_internship)

    payload = {
        "phone_number": phone_number,
        "task": script,
        "voice": BLAND_VOICE_ID if BLAND_VOICE_ID else "mason",
        "wait_for_greeting": True,
        "record": True,
        "amd": True,  # answering machine detection
        "interruption_threshold": 150,
        "max_duration": 15,
        "answered_by_enabled": True,
        "noise_cancellation": True,
        "language": "en-US",
        "metadata": {
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "job_title": job_title,
            "airtable_record_id": airtable_record_id
        },
        "webhook": f"{WEBHOOK_BASE_URL}/webhooks/bland/call-complete",
        "request_data": {
            "candidate_name": candidate_name,
            "job_title": job_title
        }
    }

    resp = requests.post(f"{BASE_URL}/calls", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def get_call_details(call_id: str) -> dict:
    """Fetch transcript, recording, and summary from a completed call."""
    resp = requests.get(f"{BASE_URL}/calls/{call_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_call_transcript(call_id: str) -> str:
    """Return plain text transcript of a call."""
    data = get_call_details(call_id)
    transcripts = data.get("transcripts", [])
    if not transcripts:
        return data.get("summary", "No transcript available.")
    lines = []
    for t in transcripts:
        speaker = "AI" if t.get("user") == "assistant" else "CANDIDATE"
        lines.append(f"{speaker}: {t.get('text', '')}")
    return "\n".join(lines)


def list_recent_calls(limit: int = 20) -> list:
    resp = requests.get(f"{BASE_URL}/calls?limit={limit}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("calls", [])


def create_inbound_agent(job_title: str = "open positions") -> dict:
    """
    Create a persistent inbound agent — candidates can call this number anytime.
    Returns a phone number you can post on job listings.
    """
    script = f"""
You are Alex, an AI recruiting assistant for {COMPANY_NAME}.
Candidates are calling in about job opportunities.

- Be warm, professional, and helpful.
- Collect their name, email, phone, and which role they're interested in.
- Ask the same screening questions as the outbound script for {job_title}.
- If they're a fit, send them the Calendly link: {CALENDLY_BOOKING_LINK}
- Always disclose you are an AI assistant.
- If they want to speak to a human, take their info and say someone will follow up within 24 hours.
"""
    payload = {
        "name": f"{COMPANY_NAME} Recruiting Line",
        "prompt": script,
        "voice": BLAND_VOICE_ID if BLAND_VOICE_ID else "mason",
        "webhook": f"{WEBHOOK_BASE_URL}/webhooks/bland/inbound",
        "language": "en-US",
        "interruptions": True
    }
    resp = requests.post(f"{BASE_URL}/agents", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()
