"""
Web pipeline dashboard — visual hiring funnel.
Run: python dashboard/app.py
Open: http://localhost:5056
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, render_template, request
import airtable_ats as ats
import email_outreach as email_out
import candidate_scorer as scorer

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/candidates")
def api_candidates():
    try:
        import requests as req
        from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES
        resp = req.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}",
            headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"},
            params={"pageSize": 100, "sort[0][field]": "Applied_Date",
                    "sort[0][direction]": "desc"}
        )
        records = resp.json().get("records", [])
        candidates = []
        for r in records:
            f = r.get("fields", {})
            candidates.append({
                "record_id":      r["id"],
                "name":           f.get("Name", "Unknown"),
                "email":          f.get("Email", ""),
                "phone":          f.get("Phone", ""),
                "job_title":      f.get("Job_Title", ""),
                "job_id":         f.get("Job_ID", ""),
                "status":         f.get("Status", "Applied"),
                "score":          f.get("Score", 0),
                "recommend":      f.get("Recommend", ""),
                "comp":           f.get("Comp_Expectation", ""),
                "availability":   f.get("Availability", ""),
                "source":         f.get("Source", ""),
                "summary":        f.get("Score_Summary", ""),
                "calendly_booked":f.get("Calendly_Booked", False),
                "applied_date":   f.get("Applied_Date", "")
            })
        return jsonify({"candidates": candidates})
    except Exception as e:
        return jsonify({"candidates": [], "error": str(e)})


@app.route("/api/jobs")
def api_jobs():
    try:
        jobs_raw = ats.get_active_jobs()
        jobs = [{
            "job_id":   j["fields"].get("Job_ID", ""),
            "title":    j["fields"].get("Job_Title", ""),
            "type":     j["fields"].get("Type", ""),
            "pay":      j["fields"].get("Pay_Range", ""),
            "status":   j["fields"].get("Status", "")
        } for j in jobs_raw]
        return jsonify({"jobs": jobs})
    except Exception as e:
        return jsonify({"jobs": [], "error": str(e)})


@app.route("/api/sequence-stats")
def api_seq_stats():
    try:
        from email_sequences import get_sequence_stats
        return jsonify(get_sequence_stats())
    except Exception:
        return jsonify({"total": 0, "active": 0})


@app.route("/api/digest")
def api_digest():
    try:
        recs    = ats.get_qualified_candidates()
        ranked  = scorer.rank_candidates_for_job(recs, "All Roles")
        summary = scorer.generate_weekly_digest(ranked)
        return f"<pre style='font-family:monospace;padding:24px;white-space:pre-wrap'>{summary}</pre>"
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/api/send-calendly", methods=["POST"])
def api_send_calendly():
    data  = request.json or {}
    email = data.get("email", "")
    name  = data.get("name", "")
    job   = data.get("job_title", "")
    try:
        email_out.send_qualified_email(name, email, job, "")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/reject", methods=["POST"])
def api_reject():
    data      = request.json or {}
    record_id = data.get("record_id", "")
    email     = data.get("email", "")
    name      = data.get("name", "")
    job       = data.get("job_title", "")
    try:
        ats.update_candidate(record_id, {"Status": "Rejected"})
        if email:
            email_out.send_rejection_email(name, email, job)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/prep/<record_id>")
def prep_packet_view(record_id):
    try:
        from prep_packet import generate_and_print
        text = generate_and_print(record_id=record_id)
        return f"<pre style='font-family:monospace;padding:28px;max-width:800px;white-space:pre-wrap'>{text}</pre>"
    except Exception as e:
        return f"Error: {e}", 500


if __name__ == "__main__":
    print("\n AI Recruiter Dashboard")
    print("  Open: http://localhost:5056\n")
    app.run(host="0.0.0.0", port=5056, debug=False)
