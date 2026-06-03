"""
1099 Contractor offer letter generator.
Generates a ready-to-sign HTML offer letter pre-filled from Airtable data.

Usage:
  python offer_letter.py --email jane@example.com --rate 35 --start 2026-07-01
"""

import argparse
from datetime import datetime
from pathlib import Path
from config import YOUR_NAME, COMPANY_NAME, YOUR_EMAIL
import airtable_ats as ats


TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 750px; margin: 60px auto; padding: 0 40px;
         color: #222; line-height: 1.7; }}
  h1   {{ font-size: 22px; text-align: center; margin-bottom: 4px; }}
  .sub {{ text-align: center; color: #555; font-size: 14px; margin-bottom: 40px; }}
  .field {{ border-bottom: 1px solid #333; display: inline-block; min-width: 200px; }}
  .section {{ margin-top: 28px; }}
  .sig-block {{ margin-top: 60px; display: flex; gap: 80px; }}
  .sig-line {{ border-top: 1px solid #333; width: 220px; margin-top: 40px; padding-top: 6px;
               font-size: 13px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  td, th {{ padding: 8px 12px; border: 1px solid #ddd; font-size: 14px; }}
  th {{ background: #f5f5f5; text-align: left; }}
  .footer {{ margin-top: 60px; font-size: 12px; color: #888; border-top: 1px solid #ddd;
             padding-top: 16px; }}
</style>
</head>
<body>

<h1>{company_name}</h1>
<div class="sub">Independent Contractor Agreement — Offer Letter</div>

<div class="section">
<p><strong>Date:</strong> {date}</p>
<p><strong>To:</strong> {candidate_name}<br>
<strong>Email:</strong> {candidate_email}</p>
</div>

<div class="section">
<p>Dear {first_name},</p>
<p>We are pleased to offer you an independent contractor engagement with <strong>{company_name}</strong>
on the following terms:</p>

<table>
  <tr><th>Role / Position</th><td>{job_title}</td></tr>
  <tr><th>Engagement Type</th><td>Independent Contractor (1099)</td></tr>
  <tr><th>Compensation</th><td><strong>{rate}</strong></td></tr>
  <tr><th>Estimated Hours</th><td>{hours}</td></tr>
  <tr><th>Proposed Start Date</th><td>{start_date}</td></tr>
  <tr><th>Duration</th><td>{duration}</td></tr>
  <tr><th>Work Location</th><td>{location}</td></tr>
</table>
</div>

<div class="section">
<p><strong>Scope of Work</strong></p>
<p>{scope}</p>
</div>

<div class="section">
<p><strong>Independent Contractor Status</strong></p>
<p>You will perform services as an independent contractor. You will not be an employee of {company_name}
and will be responsible for all applicable taxes, insurance, and benefits. You will receive a Form 1099
for any payments made during the applicable tax year.</p>
</div>

<div class="section">
<p><strong>Confidentiality</strong></p>
<p>You agree to keep all confidential business information, client data, and proprietary materials
of {company_name} strictly confidential during and after the engagement.</p>
</div>

<div class="section">
<p><strong>Intellectual Property</strong></p>
<p>Any work product, deliverables, or materials created in connection with this engagement shall
be the sole property of {company_name}.</p>
</div>

<div class="section">
<p><strong>Termination</strong></p>
<p>Either party may terminate this engagement with {notice_period} written notice.</p>
</div>

<div class="section">
<p>To accept this offer, please sign below and return a copy to
<a href="mailto:{company_email}">{company_email}</a>.</p>
<p>This offer is valid for <strong>5 business days</strong> from the date above.</p>
</div>

<div class="section">
<p>We look forward to working with you.</p>
<p>Sincerely,<br><strong>{your_name}</strong><br>{company_name}</p>
</div>

<div class="sig-block">
  <div>
    <div class="sig-line">
      Signature — {your_name}<br>{company_name}
    </div>
  </div>
  <div>
    <div class="sig-line">
      Signature — {candidate_name}<br>Date: ________________
    </div>
  </div>
</div>

<div class="footer">
This document constitutes an offer of independent contractor services and does not create an
employment relationship. {company_name} | {company_email}
</div>

</body>
</html>"""


def generate_offer_letter(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    rate: str,
    start_date: str,
    hours: str = "20-40 hrs/week",
    duration: str = "Ongoing, at-will",
    location: str = "Remote",
    scope: str = "",
    notice_period: str = "7 days"
) -> str:
    if not scope:
        scope = (f"Contractor will provide {job_title} services as directed by {YOUR_NAME}, "
                 f"including but not limited to analysis, reporting, and related deliverables.")

    html = TEMPLATE.format(
        company_name  = COMPANY_NAME,
        your_name     = YOUR_NAME,
        company_email = YOUR_EMAIL,
        date          = datetime.now().strftime("%B %d, %Y"),
        candidate_name  = candidate_name,
        candidate_email = candidate_email,
        first_name    = candidate_name.split()[0],
        job_title     = job_title,
        rate          = rate,
        hours         = hours,
        start_date    = start_date,
        duration      = duration,
        location      = location,
        scope         = scope,
        notice_period = notice_period
    )
    return html


def save_offer_letter(html: str, candidate_name: str) -> str:
    safe_name = candidate_name.replace(" ", "_")
    out_dir   = Path(__file__).parent / "offer_letters"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"offer_{safe_name}_{datetime.now().strftime('%Y%m%d')}.html"
    path.write_text(html, encoding="utf-8")
    print(f"Saved: {path}")
    return str(path)


def email_offer_letter(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    rate: str,
    start_date: str,
    **kwargs
) -> bool:
    from email_outreach import _send
    html = generate_offer_letter(candidate_name, candidate_email, job_title, rate, start_date, **kwargs)
    subject = f"Your Contractor Offer — {job_title} at {COMPANY_NAME}"
    intro = f"""
<p>Hi {candidate_name.split()[0]},</p>
<p>Great speaking with you. Please find your offer letter below. To accept, reply to this email
with your signature (typed name is fine) or sign and return the attached.</p>
<p>This offer is valid for 5 business days.</p>
<p>Looking forward to working together!<br>{YOUR_NAME}</p>
<hr style="margin:30px 0">
"""
    return _send(candidate_email, subject, intro + html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 1099 offer letter")
    parser.add_argument("--email",      required=True, help="Candidate email (pulls from Airtable)")
    parser.add_argument("--rate",       required=True, help="e.g. '$35/hr' or '$3,000/month'")
    parser.add_argument("--start",      required=True, help="Start date e.g. 2026-07-01")
    parser.add_argument("--hours",      default="20-40 hrs/week")
    parser.add_argument("--send",       action="store_true", help="Email offer to candidate")
    parser.add_argument("--save",       action="store_true", help="Save HTML to disk")
    args = parser.parse_args()

    candidate = ats.get_candidate_by_email(args.email)
    if not candidate:
        print(f"Candidate not found: {args.email}")
        exit(1)

    f     = candidate["fields"]
    name  = f.get("Name", "Candidate")
    job   = f.get("Job_Title", "Contractor Role")

    html = generate_offer_letter(name, args.email, job, args.rate, args.start, args.hours)

    if args.save:
        save_offer_letter(html, name)
    if args.send:
        email_offer_letter(name, args.email, job, args.rate, args.start, args.hours)
        print(f"Offer sent to {args.email}")
    if not args.save and not args.send:
        print(html[:500] + "\n... (use --save or --send)")
