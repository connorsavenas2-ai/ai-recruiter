"""
Flask webhook server — fully free version.
Receives events from:
  - Calendly (interview booked/canceled)
  - Job boards via Zapier free tier (new application)
  - Manual trigger endpoint

Run: python webhook_server.py
Expose with: ngrok http 5055  (free)
"""

import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

import airtable_ats as ats
import email_outreach as email_out
import candidate_scorer as scorer
from config import CALENDLY_BOOKING_LINK
from scheduling import start_scheduler, handle_cancellation, send_calendly_to_qualified

app = Flask(__name__)
CORS(app)


# ── NEW APPLICATION ───────────────────────────────────────────────────────────
# Zapier sends here when someone applies on Indeed/LinkedIn/Handshake

@app.route("/webhooks/application", methods=["POST"])
def new_application():
    """
    Receives new job applications from Zapier.

    Zapier setup (free tier, 100 tasks/mo):
      Trigger: New Applicant in Indeed / LinkedIn Jobs
      Action:  Webhooks by Zapier → POST to this URL
      Data:    name, email, phone, job_title, job_id, source, resume_text
    """
    data       = request.json or {}
    name       = data.get("name", "").strip()
    email_addr = data.get("email", "").strip()
    phone      = data.get("phone", "").strip()
    job_title  = data.get("job_title", "").strip()
    job_id     = data.get("job_id", "").strip()
    source     = data.get("source", "Unknown")
    resume     = data.get("resume_text", "")

    if not name or not email_addr:
        return jsonify({"error": "name and email required"}), 400

    print(f"[APP] New application: {name} for {job_title} via {source}")

    def process():
        try:
            # 1. Add to Airtable
            record    = ats.create_candidate(name, email_addr, phone, job_title, job_id, source)
            record_id = record["id"]

            # 2. Score based on resume/application text if provided
            if resume:
                jobs    = ats.get_active_jobs()
                job_obj = next((j for j in jobs if j["fields"].get("Job_ID") == job_id), {})
                job_desc = job_obj.get("fields", {}).get("Description", job_title)
                job_req  = job_obj.get("fields", {}).get("Requirements", "")

                score_data = scorer.score_candidate_from_resume(
                    resume, name, job_title, job_desc, job_req
                )
                score     = score_data.get("score", 0)
                recommend = score_data.get("recommend", "No")
                summary   = score_data.get("summary", "")
                strengths = "\n".join(score_data.get("strengths", []))
                concerns  = "\n".join(score_data.get("concerns", []))
                comp      = score_data.get("comp_expectation", "Unknown")
                avail     = score_data.get("availability", "Unknown")

                ats.update_candidate_after_call(
                    record_id, "resume-screen", score, summary,
                    strengths, concerns, comp, avail, recommend, resume
                )
                print(f"[SCORE] {name}: {score}/10 — {recommend}")

                # 3. Act on score
                if score >= 7:
                    record = ats.get_candidate_by_email(email_addr)
                    rid    = record["id"] if record else ""
                    send_calendly_to_qualified(rid, name, email_addr, phone, job_title)
                    print(f"[EMAIL+SMS] Sent Calendly invite to {name}")
                elif score <= 4:
                    email_out.send_rejection_email(name, email_addr, job_title)
                    print(f"[EMAIL] Sent rejection to {name}")
                else:
                    # Middle scores — send a "we'll be in touch" holding email
                    email_out.send_holding_email(name, email_addr, job_title)
            else:
                # No resume text — just acknowledge and put in queue for manual review
                email_out.send_application_received_email(name, email_addr, job_title)
                print(f"[EMAIL] Sent application acknowledgment to {name}")

        except Exception as e:
            print(f"[ERROR] Processing application {name}: {e}")
            import traceback; traceback.print_exc()

    threading.Thread(target=process, daemon=True).start()
    return jsonify({"ok": True})


# ── CALENDLY WEBHOOK ──────────────────────────────────────────────────────────

@app.route("/webhooks/calendly", methods=["POST"])
def calendly_webhook():
    data  = request.json or {}
    event = data.get("event", "")
    inv   = data.get("payload", {}).get("invitee", {})

    name       = inv.get("name", "Unknown")
    email_addr = inv.get("email", "")
    start_time = data.get("payload", {}).get("event", {}).get("start_time", "")
    join_url   = data.get("payload", {}).get("event", {}).get("location", {}).get("join_url", "")

    print(f"[CALENDLY] {event}: {name} at {start_time}")

    if event == "invitee.created":
        formatted = start_time
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            formatted = dt.strftime("%A, %B %d at %I:%M %p ET")
        except Exception:
            pass

        existing = ats.get_candidate_by_email(email_addr)
        if existing:
            ats.mark_calendly_booked(existing["id"], start_time[:10])

        if email_addr:
            email_out.send_interview_confirmation(name, email_addr, "Final Interview", formatted, join_url)

        print(f"[ACTION] Interview confirmed: {name} at {formatted}")

    elif event == "invitee.canceled":
        print(f"[CALENDLY] {name} canceled — sending rebook offer")
        cand  = ats.get_candidate_by_email(email_addr)
        phone = cand["fields"].get("Phone", "") if cand else ""
        threading.Thread(
            target=handle_cancellation,
            args=(name, email_addr, "your upcoming interview", phone),
            daemon=True
        ).start()
        if cand:
            ats.update_candidate(cand["id"], {"Calendly_Booked": False,
                                               "Status": "Qualified"})

    return jsonify({"ok": True})


# ── MANUAL TRIGGER (test any candidate) ──────────────────────────────────────

@app.route("/trigger/score", methods=["POST"])
def manual_score():
    """Manually score a candidate by record ID or re-process with resume."""
    data      = request.json or {}
    record_id = data.get("record_id", "")
    resume    = data.get("resume_text", "")
    job_title = data.get("job_title", "General Role")

    if not record_id:
        return jsonify({"error": "record_id required"}), 400

    score_data = scorer.score_candidate_from_resume(resume, "Candidate", job_title, "", "")
    return jsonify(score_data)


# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "mode": "free-tier"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "AI Recruiter (Free Mode)",
        "endpoints": [
            "POST /webhooks/application  ← Zapier sends here",
            "POST /webhooks/calendly     ← Calendly sends here",
            "POST /trigger/score         ← Manual scoring",
            "GET  /health"
        ]
    })


if __name__ == "__main__":
    start_scheduler()   # start reminders, follow-ups, no-show detection
    print("\n AI Recruiter + Jenny Webhook Server")
    print("=" * 42)
    print("  Running on: http://localhost:5055")
    print("  Expose with: ngrok http 5055")
    print("  Scheduler: booking follow-ups, 24hr/1hr reminders, no-show detection")
    print("  Then paste ngrok URL into .env as WEBHOOK_BASE_URL\n")
    app.run(host="0.0.0.0", port=5055, debug=False)
