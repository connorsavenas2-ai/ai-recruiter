"""
Referral engine — emails your network asking for candidate referrals.
Tracks referrals in Airtable with source attribution.

Flask endpoint: GET /refer/<job_id>  → referral form
               POST /refer/<job_id>  → submits referral
"""

import json
from config import get_ai_client, YOUR_NAME, COMPANY_NAME, YOUR_EMAIL, WEBHOOK_BASE_URL
from email_outreach import _send
import airtable_ats as ats


REFERRAL_FORM_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Refer a Candidate — {company}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 520px; margin: 60px auto;
         padding: 0 24px; color: #111; }}
  h2   {{ margin-bottom: 4px; }}
  .sub {{ color: #666; margin-bottom: 32px; font-size: 15px; }}
  label {{ display: block; font-weight: 600; margin-bottom: 4px; margin-top: 20px; }}
  input, textarea {{ width: 100%; padding: 10px; border: 1px solid #ccc;
                     border-radius: 6px; font-size: 15px; box-sizing: border-box; }}
  textarea {{ height: 90px; resize: vertical; }}
  button {{ margin-top: 24px; width: 100%; padding: 12px;
            background: #2F5496; color: white; border: none;
            border-radius: 6px; font-size: 16px; cursor: pointer; }}
  button:hover {{ background: #1e3a6e; }}
  .job-card {{ background: #f5f7ff; border-left: 4px solid #2F5496;
               padding: 14px 18px; border-radius: 4px; margin-bottom: 28px; }}
</style>
</head>
<body>
<h2>Know someone great?</h2>
<p class="sub">Refer a candidate for this role at {company}. It only takes 60 seconds.</p>

<div class="job-card">
  <strong>{job_title}</strong><br>
  <span style="color:#555;font-size:14px">{job_type} &nbsp;·&nbsp; {pay_range}</span>
</div>

<form method="POST">
  <label>Their Name *</label>
  <input name="ref_name" required placeholder="Jane Smith">

  <label>Their Email *</label>
  <input name="ref_email" type="email" required placeholder="jane@example.com">

  <label>Their Phone (optional)</label>
  <input name="ref_phone" placeholder="+1 (555) 000-0000">

  <label>Why are they a great fit? (optional)</label>
  <textarea name="ref_notes" placeholder="e.g. 3 years finance experience, great with Excel..."></textarea>

  <label>Your Name (so we can thank you)</label>
  <input name="referrer_name" placeholder="Your name">

  <button type="submit">Submit Referral →</button>
</form>
</body>
</html>"""

REFERRAL_THANKS_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>
  body {{ font-family: -apple-system, sans-serif; max-width: 480px; margin: 80px auto;
         padding: 0 24px; text-align: center; }}
  h2 {{ color: #2F5496; }}
</style></head>
<body>
<h2>Thank you! 🎉</h2>
<p>We received your referral for <strong>{ref_name}</strong>.</p>
<p>We'll reach out to them shortly. If they get hired, we'll make sure to thank you properly!</p>
<p style="color:#888;font-size:13px;margin-top:40px">{company}</p>
</body>
</html>"""


def send_referral_blast(job_id: str, contacts: list[dict]) -> int:
    """
    Send a referral ask email to a list of contacts.
    contacts: [{"name": "...", "email": "..."}, ...]
    """
    jobs    = ats.get_active_jobs()
    job_obj = next((j for j in jobs if j["fields"].get("Job_ID") == job_id), {})
    if not job_obj:
        raise ValueError(f"Job {job_id} not found")

    f         = job_obj["fields"]
    job_title = f.get("Job_Title", "")
    pay       = f.get("Pay_Range", "Competitive")
    job_type  = f.get("Type", "1099")
    ref_url   = f"{WEBHOOK_BASE_URL}/refer/{job_id}"

    client, model = get_ai_client()
    prompt = f"""Write a short, friendly referral ask email from {YOUR_NAME} to someone in their professional network.

Role: {job_title} ({job_type}, {pay})
Referral link: {ref_url}

Make it feel like a genuine personal ask — not a mass blast. Short: 3-4 sentences.
End with: "Click here to refer someone in 60 seconds: [LINK]"

Return ONLY valid JSON: {{"subject": "...", "body_html": "...", "body_text": "..."}}"""

    resp     = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        max_tokens=400, temperature=0.5
    )
    raw      = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw  = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    template = json.loads(raw.strip())

    sent = 0
    for contact in contacts:
        body_html = template["body_html"].replace("[LINK]", f'<a href="{ref_url}">{ref_url}</a>')
        body_text = template["body_text"].replace("[LINK]", ref_url)
        body_html = body_html.replace("{name}", contact["name"].split()[0])
        body_text = body_text.replace("{name}", contact["name"].split()[0])
        try:
            _send(contact["email"], template["subject"], body_html, body_text)
            sent += 1
        except Exception as e:
            print(f"  Error sending to {contact['email']}: {e}")

    return sent


def register_referral_routes(app):
    """Add referral form routes to the Flask app."""
    from flask import request, make_response

    @app.route("/refer/<job_id>", methods=["GET"])
    def referral_form(job_id):
        jobs    = ats.get_active_jobs()
        job_obj = next((j for j in jobs if j["fields"].get("Job_ID") == job_id), {})
        f       = job_obj.get("fields", {}) if job_obj else {}
        html    = REFERRAL_FORM_HTML.format(
            company   = COMPANY_NAME,
            job_title = f.get("Job_Title", "Open Role"),
            job_type  = f.get("Type", "1099"),
            pay_range = f.get("Pay_Range", "Competitive")
        )
        return make_response(html, 200, {"Content-Type": "text/html"})

    @app.route("/refer/<job_id>", methods=["POST"])
    def referral_submit(job_id):
        from flask import request
        ref_name     = request.form.get("ref_name", "").strip()
        ref_email    = request.form.get("ref_email", "").strip()
        ref_phone    = request.form.get("ref_phone", "").strip()
        ref_notes    = request.form.get("ref_notes", "").strip()
        referrer     = request.form.get("referrer_name", "Anonymous")

        jobs    = ats.get_active_jobs()
        job_obj = next((j for j in jobs if j["fields"].get("Job_ID") == job_id), {})
        job_t   = job_obj.get("fields", {}).get("Job_Title", "Open Role") if job_obj else "Open Role"

        if ref_name and ref_email:
            ats.create_candidate(
                ref_name, ref_email, ref_phone, job_t, job_id,
                source="Referral",
                notes=f"Referred by: {referrer}\n{ref_notes}"
            )
            # Notify Connor
            _send(YOUR_EMAIL,
                  f"New Referral: {ref_name} for {job_t}",
                  f"<p><b>{ref_name}</b> ({ref_email}) was referred by <b>{referrer}</b>.<br>"
                  f"Notes: {ref_notes or 'None'}</p>")

        thanks = REFERRAL_THANKS_HTML.format(ref_name=ref_name, company=COMPANY_NAME)
        return make_response(thanks, 200, {"Content-Type": "text/html"})
