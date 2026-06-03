"""
SMS outreach via Twilio — sends texts to candidates after screening calls,
follow-ups, and Calendly booking links.
"""

"""
SMS via free email-to-carrier gateways (default) or Twilio (if configured).
No account or payment needed for the free gateway approach.
"""
from config import TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE, YOUR_NAME, COMPANY_NAME, CALENDLY_BOOKING_LINK
import os


def send_sms(to: str, message: str, carrier: str = "") -> str:
    """
    Send SMS. Uses free carrier email gateways by default.
    Falls back to Twilio if TWILIO_ACCOUNT_SID is set.
    """
    if TWILIO_SID:
        try:
            from twilio.rest import Client
            msg = Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
                body=message, from_=TWILIO_PHONE, to=to)
            return msg.sid
        except Exception as e:
            print(f"[SMS] Twilio failed ({e}), trying free gateway...")

    # Free gateway fallback
    from free_sms import send_free_sms
    send_free_sms(to, message, carrier)
    return "free-gateway"


def sms_calendly_link(candidate_name: str, phone: str, job_title: str) -> str:
    message = (
        f"Hi {candidate_name.split()[0]}! This is the AI recruiting assistant for {YOUR_NAME} "
        f"at {COMPANY_NAME}. Great speaking with you about the {job_title} role. "
        f"Here's your link to book your final interview with {YOUR_NAME}: "
        f"{CALENDLY_BOOKING_LINK} — takes 30 seconds!"
    )
    return send_sms(phone, message)


def sms_interview_reminder(candidate_name: str, phone: str, interview_datetime: str) -> str:
    message = (
        f"Hi {candidate_name.split()[0]}, just a reminder your interview with {YOUR_NAME} "
        f"is scheduled for {interview_datetime}. Reply CONFIRM to confirm or "
        f"RESCHEDULE if you need a different time."
    )
    return send_sms(phone, message)


def sms_followup_no_answer(candidate_name: str, phone: str, job_title: str) -> str:
    message = (
        f"Hi {candidate_name.split()[0]}, this is an AI assistant for {YOUR_NAME} "
        f"at {COMPANY_NAME}. We tried calling about the {job_title} role. "
        f"Interested? Reply YES and we'll reach back out, or visit: {CALENDLY_BOOKING_LINK}"
    )
    return send_sms(phone, message)


def sms_new_application_ack(candidate_name: str, phone: str, job_title: str) -> str:
    message = (
        f"Hi {candidate_name.split()[0]}! We received your application for {job_title} "
        f"at {COMPANY_NAME}. Our AI recruiter will call you within 24 hours for a quick 10-min screen. "
        f"Reply STOP to opt out."
    )
    return send_sms(phone, message)
