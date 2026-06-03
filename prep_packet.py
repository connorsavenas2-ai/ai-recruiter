"""
Pre-interview prep packet generator.
Run before a final-round interview to get a one-page brief:
  - Candidate summary
  - Strengths / concerns
  - 5 tailored interview questions
  - Comp expectation
  - Recommended decision framework

Usage:
  python prep_packet.py --email jane@example.com
  python prep_packet.py --record-id recXXXXXXXXXXXXXX
"""

import argparse
import json
from datetime import datetime
from config import get_ai_client, YOUR_NAME, COMPANY_NAME
import airtable_ats as ats


def generate_prep_packet(candidate: dict) -> str:
    """Generate a full interview prep brief for Connor."""
    f          = candidate.get("fields", {})
    name       = f.get("Name", "Candidate")
    job        = f.get("Job_Title", "")
    score      = f.get("Score", "N/A")
    summary    = f.get("Score_Summary", "")
    strengths  = f.get("Strengths", "")
    concerns   = f.get("Concerns", "")
    comp       = f.get("Comp_Expectation", "Unknown")
    avail      = f.get("Availability", "Unknown")
    transcript = f.get("Transcript", "")[:2000]
    recommend  = f.get("Recommend", "")
    source     = f.get("Source", "")

    client, model = get_ai_client()

    prompt = f"""You are a recruiting assistant preparing a final-round interview brief for {YOUR_NAME} at {COMPANY_NAME}.

CANDIDATE: {name}
ROLE: {job}
SCORE: {score}/10
RECOMMEND: {recommend}
SOURCE: {source}
COMP EXPECTATION: {comp}
AVAILABILITY: {avail}

RECRUITER SUMMARY:
{summary}

STRENGTHS:
{strengths}

CONCERNS:
{concerns}

TRANSCRIPT/RESUME EXCERPT:
{transcript}

Generate a concise, scannable prep brief for the hiring manager. Include:

1. **One-line verdict** (hire / strong maybe / pass + why in 10 words)
2. **Candidate snapshot** (3 bullet points — who they are, what they bring)
3. **Top 3 strengths** (specific, evidence-based)
4. **Top 2 concerns** (honest, actionable)
5. **5 tailored interview questions** (based on gaps/strengths, not generic)
6. **Comp & availability** (clear summary)
7. **How to close them** (what would make this candidate say yes — based on what they said)
8. **Red flags to probe** (anything that needs clarification)

Be direct and useful. {YOUR_NAME} has 2 minutes to read this before the call."""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


def generate_and_print(email: str = "", record_id: str = "") -> str:
    candidate = None
    if email:
        candidate = ats.get_candidate_by_email(email)
    elif record_id:
        import requests
        from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES
        url  = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"})
        candidate = resp.json()

    if not candidate:
        return "Candidate not found."

    packet = generate_prep_packet(candidate)

    name = candidate.get("fields", {}).get("Name", "Candidate")
    now  = datetime.now().strftime("%b %d, %Y %I:%M %p")

    output = f"""
{'='*60}
INTERVIEW PREP — {name.upper()}
Generated: {now}
{'='*60}

{packet}

{'='*60}
"""
    print(output)
    return output


def email_prep_packet_to_connor(email: str = "", record_id: str = "") -> bool:
    """Email the prep packet to Connor before the interview."""
    from email_outreach import _send
    from config import YOUR_EMAIL

    packet_text = generate_and_print(email, record_id)

    if email:
        cand = ats.get_candidate_by_email(email)
        name = cand.get("fields", {}).get("Name", "Candidate") if cand else email
    else:
        name = record_id

    subject  = f"Interview Prep: {name} — Ready for your call"
    html     = f"<pre style='font-family:monospace;font-size:13px'>{packet_text}</pre>"
    return _send(YOUR_EMAIL, subject, html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate interview prep packet")
    parser.add_argument("--email",     help="Candidate email")
    parser.add_argument("--record-id", help="Airtable record ID")
    parser.add_argument("--send",      action="store_true", help="Email packet to Connor")
    args = parser.parse_args()

    if not args.email and not args.record_id:
        parser.print_help()
    elif args.send:
        email_prep_packet_to_connor(args.email or "", args.record_id or "")
        print(f"Prep packet emailed to {__import__('config').YOUR_EMAIL}")
    else:
        generate_and_print(args.email or "", args.record_id or "")
