"""
Hiring Dashboard — full ATS web app.
Run locally:  python ats/app.py
Deploy:       see render.yaml
"""

import sys, json, os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, session
from flask_cors import CORS
import requests as req

from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES, AIRTABLE_JOBS
import airtable_ats as ats
import email_outreach as email_out
from ats.auth import verify_login, login_user, logout_user, current_user, login_required

COMPANY_NAME = os.getenv("COMPANY_NAME", "Connor Savenas Ventures")

app = Flask(__name__, template_folder="templates", static_folder="static",
            static_url_path="/ats/static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production-abc123xyz")
app.permanent_session_lifetime = timedelta(days=30)
CORS(app)

AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}


def _render(template, **kwargs):
    """Render with auth context injected into every template."""
    return render_template(template,
                           current_user=current_user(),
                           company_name=COMPANY_NAME,
                           **kwargs)


# ── AUTH ROUTES ───────────────────────────────────────────────────────────────

@app.route("/ats/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect("/ats/")
    error = None
    next_url = request.args.get("next") or request.form.get("next") or "/ats/"
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = verify_login(username, password)
        if user:
            login_user(user["username"], user["display_name"], user["role"], user["avatar"])
            return redirect(next_url)
        error = "Invalid username or password."
    return render_template("login.html", error=error, next=next_url,
                           company_name=COMPANY_NAME)


@app.route("/ats/logout")
def logout():
    logout_user()
    return redirect("/ats/login")


def _at_get(table, params=None):
    resp = req.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}",
                   headers=AT_HEADERS, params=params or {})
    return resp.json()


def _map_candidate(r):
    f = r.get("fields", {})
    return {
        "record_id":           r["id"],
        "name":                f.get("Name", ""),
        "email":               f.get("Email", ""),
        "phone":               f.get("Phone", ""),
        "job_title":           f.get("Job_Title", ""),
        "job_id":              f.get("Job_ID", ""),
        "status":              f.get("Status", "Applied"),
        "score":               f.get("Score", 0),
        "score_summary":       f.get("Score_Summary", ""),
        "strengths":           f.get("Strengths", ""),
        "concerns":            f.get("Concerns", ""),
        "comp_expectation":    f.get("Comp_Expectation", ""),
        "availability":        f.get("Availability", ""),
        "call_id":             f.get("Call_ID", ""),
        "call_recording_url":  f.get("Call_Recording_URL", ""),
        "transcript":          f.get("Transcript", ""),
        "source":              f.get("Source", ""),
        "notes":               f.get("Notes", ""),
        "calendly_booked":     f.get("Calendly_Booked", False),
        "recommend":           f.get("Recommend", ""),
        "applied_date":        f.get("Applied_Date", ""),
        "called_date":         f.get("Called_Date", ""),
        "final_interview_date":f.get("Final_Interview_Date", ""),
        "comp":                f.get("Comp_Expectation", ""),
    }


def _map_job(r):
    f = r.get("fields", {})
    return {
        "record_id":   r["id"],
        "job_id":      f.get("Job_ID", ""),
        "title":       f.get("Job_Title", ""),
        "type":        f.get("Type", "1099"),
        "description": f.get("Description", ""),
        "requirements":f.get("Requirements", ""),
        "pay":         f.get("Pay_Range", ""),
        "status":      f.get("Status", "Active"),
        "posted_date": f.get("Posted_Date", ""),
    }


# ── PAGES ────────────────────────────────────────────────────────────────────

@app.route("/ats/")
@app.route("/ats")
@login_required
def dashboard():
    return _render("dashboard.html", page="dashboard", hour=datetime.now().hour)


@app.route("/ats/candidates")
@login_required
def candidates_page():
    return _render("candidates.html", page="candidates")


@app.route("/ats/candidates/<record_id>")
@login_required
def candidate_detail(record_id):
    resp = req.get(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}",
        headers=AT_HEADERS
    )
    if resp.status_code != 200:
        return redirect("/ats/candidates")
    candidate = _map_candidate(resp.json())
    return _render("candidate_detail.html", page="candidates", candidate=candidate)


@app.route("/ats/jobs")
@login_required
def jobs_page():
    return _render("jobs.html", page="jobs")


@app.route("/ats/jobs/new")
@login_required
def new_job_page():
    return _render("new_job.html", page="jobs")


@app.route("/ats/jobs/<record_id>")
@login_required
def job_detail(record_id):
    return redirect("/ats/jobs")


@app.route("/ats/pipeline")
@login_required
def pipeline_page():
    return _render("pipeline.html", page="pipeline")


@app.route("/ats/analytics")
@login_required
def analytics_page():
    return _render("analytics.html", page="analytics")


@app.route("/ats/outreach")
@login_required
def outreach_page():
    return redirect("/ats/")


@app.route("/ats/interviews")
@login_required
def interviews_page():
    return redirect("/ats/")


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/ats/api/candidates")
def api_candidates():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
        data  = _at_get(AIRTABLE_CANDIDATES, {
            "pageSize": min(limit, 100),
            "sort[0][field]": "Applied_Date",
            "sort[0][direction]": "desc"
        })
        records    = data.get("records", [])
        candidates = [_map_candidate(r) for r in records]

        # Compute summary stats
        from datetime import datetime, timedelta
        week_ago   = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        total_week = sum(1 for c in candidates if c.get("applied_date", "") >= week_ago)
        qualified  = sum(1 for c in candidates if (c.get("score") or 0) >= 7)
        booked     = sum(1 for c in candidates if c.get("calendly_booked"))
        hired      = sum(1 for c in candidates if c.get("status") == "Hired")

        stages = ["Applied","Called","Screened","Qualified","Final_Round","Hired","Rejected"]
        funnel = {s: sum(1 for c in candidates if c.get("status") == s) for s in stages}

        return jsonify({
            "candidates": candidates,
            "total": len(candidates),
            "total_week": total_week,
            "qualified": qualified,
            "booked": booked,
            "hired": hired,
            "funnel": funnel
        })
    except Exception as e:
        return jsonify({"candidates": [], "error": str(e)})


@app.route("/ats/api/candidates", methods=["POST"])
def api_create_candidate():
    data = request.json or {}
    try:
        rec = ats.create_candidate(
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            job_title=data.get("job_title", ""),
            source=data.get("source", "Manual"),
            notes=data.get("notes", "")
        )
        return jsonify({"ok": True, "record_id": rec["id"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/candidates/<record_id>", methods=["PATCH"])
def api_update_candidate(record_id):
    data = request.json or {}
    try:
        resp = req.patch(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}",
            headers=AT_HEADERS,
            json={"fields": data}
        )
        resp.raise_for_status()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/jobs")
def api_jobs():
    try:
        data = _at_get(AIRTABLE_JOBS, {"sort[0][field]": "Posted_Date",
                                        "sort[0][direction]": "desc"})
        return jsonify({"jobs": [_map_job(r) for r in data.get("records", [])]})
    except Exception as e:
        return jsonify({"jobs": [], "error": str(e)})


@app.route("/ats/api/jobs", methods=["POST"])
def api_create_job():
    data = request.json or {}
    try:
        rec = ats.create_job(
            title=data.get("title", ""),
            job_type=data.get("type", "1099"),
            description=data.get("description", ""),
            requirements=data.get("requirements", ""),
            pay_range=data.get("pay", "")
        )
        return jsonify({"ok": True, "record_id": rec["id"],
                        "job_id": rec["fields"]["Job_ID"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/counts")
def api_counts():
    try:
        jobs  = _at_get(AIRTABLE_JOBS, {"filterByFormula": "{Status}='Active'"})
        cands = _at_get(AIRTABLE_CANDIDATES, {"pageSize": 5,
                        "sort[0][field]": "Applied_Date",
                        "sort[0][direction]": "desc"})
        from datetime import datetime, timedelta
        week_ago  = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        new_today = sum(1 for r in cands.get("records", [])
                        if r.get("fields", {}).get("Applied_Date", "") >= week_ago)
        return jsonify({
            "active_jobs": len(jobs.get("records", [])),
            "new_today": new_today
        })
    except:
        return jsonify({"active_jobs": 0, "new_today": 0})


@app.route("/ats/api/send-calendly", methods=["POST"])
def api_send_calendly():
    data = request.json or {}
    try:
        email_out.send_qualified_email(
            data.get("name", ""), data.get("email", ""),
            data.get("job_title", ""), ""
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/reject", methods=["POST"])
def api_reject():
    data = request.json or {}
    try:
        ats.update_candidate(data.get("record_id", ""), {"Status": "Rejected"})
        if data.get("email"):
            email_out.send_rejection_email(
                data.get("name", ""), data["email"], data.get("job_title", ""))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/prep/<record_id>")
def api_prep(record_id):
    try:
        resp = req.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}",
            headers=AT_HEADERS
        )
        from prep_packet import generate_prep_packet
        text = generate_prep_packet(resp.json())
        return jsonify({"prep": text})
    except Exception as e:
        return jsonify({"prep": f"Error: {e}"}), 500


@app.route("/ats/api/enroll-sequence", methods=["POST"])
def api_enroll():
    data = request.json or {}
    try:
        from email_sequences import enroll
        seq_id = enroll(data.get("email",""), data.get("name",""),
                        data.get("job_title",""), airtable_id=data.get("record_id",""))
        return jsonify({"ok": True, "sequence_id": seq_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/ats/api/ai-improve-jd", methods=["POST"])
def api_improve_jd():
    data  = request.json or {}
    title = data.get("title", "")
    desc  = data.get("description", "")
    try:
        from config import get_ai_client
        client, model = get_ai_client()
        prompt = f"""Improve this job description for a 1099 contractor role. Make it compelling and clear.

Title: {title}
Current description: {desc or "(none yet)"}

Return JSON:
{{"improved_description": "...", "requirements": "...", "suggestion": "one line tip"}}"""
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":prompt}],
            max_tokens=500, temperature=0.4
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        return jsonify(json.loads(raw.strip()))
    except Exception as e:
        return jsonify({"suggestion": str(e)}), 500


# Redirect root to ATS
@app.route("/")
def root():
    return redirect("/ats/")


if __name__ == "__main__":
    print("\n  Connor's ATS")
    print("  Open: http://localhost:5057\n")
    app.run(host="0.0.0.0", port=5057, debug=False)
