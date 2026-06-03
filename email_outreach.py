"""
Email outreach engine — sends via Gmail API (OAuth, no app password needed).
Falls back to SMTP app password if Gmail API is not authorized yet.
"""

import base64
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import OUTREACH_EMAIL, GMAIL_APP_PASSWORD, YOUR_NAME, COMPANY_NAME, CALENDLY_BOOKING_LINK, get_ai_client


def _send_gmail_api(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send via Gmail API — free, no app password needed. Requires google_token.pickle."""
    from google_auth import get_gmail_service
    service = get_gmail_service()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or ""
    msg["From"]    = f"Jenny | {COMPANY_NAME} <{OUTREACH_EMAIL}>"
    msg["To"]      = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))
    else:
        msg.attach(MIMEText(text_body or subject, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True


def _send_smtp(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Fallback: SMTP with app password."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Jenny | {COMPANY_NAME} <{OUTREACH_EMAIL}>"
    msg["To"]      = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(OUTREACH_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(OUTREACH_EMAIL, to, msg.as_string())
    return True


def _send(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Smart send: tries Gmail API first (free, no app password),
    falls back to SMTP if not yet authorized.
    """
    from pathlib import Path
    # Try Gmail API first
    if Path("google_token.pickle").exists():
        try:
            return _send_gmail_api(to, subject, html_body, text_body)
        except Exception as e:
            print(f"[EMAIL] Gmail API failed ({e}), trying SMTP...")

    # Fall back to SMTP
    if GMAIL_APP_PASSWORD:
        return _send_smtp(to, subject, html_body, text_body)

    print(f"[EMAIL] No auth configured. Run: python google_auth.py")
    print(f"[EMAIL] Would have sent to {to}: {subject}")
    return False


def generate_outreach_email(
    candidate_name: str,
    job_title: str,
    job_description: str,
    candidate_background: str = ""
) -> dict:
    """Use free AI to write a personalized outreach email."""
    client, model = get_ai_client()
    prompt = f"""Write a short, warm, personalized cold outreach email to recruit a candidate.

Sender: {YOUR_NAME} at {COMPANY_NAME}
Job: {job_title}
Description: {job_description}
Candidate: {candidate_name}
Background: {candidate_background}
Type: 1099 contractor or internship (be transparent)

- Subject: specific and compelling, not generic
- Body: 3-4 short paragraphs, conversational, real-person tone
- Mention 1099/contractor type
- Clear call to action: reply or book a call
- No hollow phrases like "I hope this finds you well"
- Max 150 words

Return ONLY valid JSON, no markdown:
{{"subject": "...", "body_html": "...", "body_text": "..."}}"""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.4
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def send_outreach_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    job_description: str,
    candidate_background: str = ""
) -> bool:
    email_data = generate_outreach_email(candidate_name, job_title, job_description, candidate_background)
    return _send(candidate_email, email_data["subject"], email_data["body_html"], email_data["body_text"])


def send_qualified_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    score_summary: str
) -> bool:
    subject = f"Next Steps — {job_title} at {COMPANY_NAME}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>Thank you for taking the time to speak with our AI recruiting assistant today about the <strong>{job_title}</strong> role at {COMPANY_NAME}.</p>
<p>Based on our conversation, we'd love to move you forward to a final interview with {YOUR_NAME} directly. Please use the link below to book a time that works for you:</p>
<p><a href="{CALENDLY_BOOKING_LINK}" style="background:#2F5496;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Schedule Your Interview →</a></p>
<p>The call will be 20-30 minutes and is your chance to ask any questions and learn more about the role.</p>
<p>Looking forward to connecting soon.</p>
<p>Best,<br>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)


def send_rejection_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str
) -> bool:
    subject = f"Your Application – {job_title} at {COMPANY_NAME}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>Thank you for your interest in the <strong>{job_title}</strong> role at {COMPANY_NAME} and for taking the time to speak with us.</p>
<p>After reviewing all candidates, we've decided to move forward with others whose experience more closely matches what we need right now.</p>
<p>We genuinely appreciate your time and encourage you to keep an eye out for future opportunities with us.</p>
<p>Best of luck in your search,<br>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)


def send_interview_confirmation(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    interview_datetime: str,
    zoom_link: str = ""
) -> bool:
    subject = f"Interview Confirmed — {job_title} with {YOUR_NAME}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>Your interview for the <strong>{job_title}</strong> position is confirmed!</p>
<p><strong>Date/Time:</strong> {interview_datetime}</p>
{"<p><strong>Zoom Link:</strong> <a href='" + zoom_link + "'>" + zoom_link + "</a></p>" if zoom_link else ""}
<p>The interview will be with <strong>{YOUR_NAME}</strong> and will run approximately 30 minutes.
Feel free to prepare any questions about the role, company, or next steps.</p>
<p>If you need to reschedule, please do so at least 24 hours in advance.</p>
<p>Looking forward to speaking with you!</p>
<p>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)


def send_application_received_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str
) -> bool:
    subject = f"We received your application — {job_title}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>Thank you for applying for the <strong>{job_title}</strong> position at {COMPANY_NAME}.</p>
<p>We're reviewing applications now and will be in touch within 2-3 business days if there's a strong fit.</p>
<p>Best,<br>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)


def send_holding_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str
) -> bool:
    subject = f"Your application is under review — {job_title}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>Thank you for your interest in the <strong>{job_title}</strong> role at {COMPANY_NAME}.</p>
<p>Your background looks promising. We're finishing our initial review and will follow up shortly with next steps.</p>
<p>Best,<br>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)


def send_calendly_followup_sms_via_email(
    candidate_name: str,
    candidate_email: str,
    job_title: str
) -> bool:
    """Follow-up email after screening call to push Calendly booking."""
    subject = f"Book Your Interview — {job_title}"
    html = f"""
<p>Hi {candidate_name},</p>
<p>It was great chatting with you earlier about the <strong>{job_title}</strong> role.</p>
<p>Here's your link to book a final interview with {YOUR_NAME}:</p>
<p><a href="{CALENDLY_BOOKING_LINK}">{CALENDLY_BOOKING_LINK}</a></p>
<p>Takes less than a minute — just pick a time that works for you.</p>
<p>{YOUR_NAME}<br>{COMPANY_NAME}</p>
"""
    return _send(candidate_email, subject, html)
