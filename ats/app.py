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


# ── BULK ACTIONS ─────────────────────────────────────────────────────────────

@app.route("/ats/api/bulk", methods=["POST"])
@login_required
def api_bulk():
    data       = request.json or {}
    record_ids = data.get("record_ids", [])
    action     = data.get("action", "")
    value      = data.get("value", "")
    done, errors = 0, 0
    for rid in record_ids:
        try:
            if action == "status":
                ats.update_candidate(rid, {"Status": value})
            elif action == "reject_with_email":
                cand_resp = req.get(
                    f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{rid}",
                    headers=AT_HEADERS)
                f = cand_resp.json().get("fields", {})
                ats.update_candidate(rid, {"Status": "Rejected"})
                if f.get("Email"):
                    email_out.send_rejection_email(f.get("Name",""), f["Email"], f.get("Job_Title",""))
            done += 1
        except:
            errors += 1
    return jsonify({"ok": True, "updated": done, "errors": errors})


# ── SCORECARD ─────────────────────────────────────────────────────────────────

@app.route("/ats/api/scorecard", methods=["POST"])
@login_required
def api_scorecard():
    data      = request.json or {}
    record_id = data.get("record_id", "")
    ratings   = data.get("ratings", {})
    notes     = data.get("notes", "")
    decision  = data.get("decision", "")
    interviewer = current_user().get("display_name", "")
    scorecard_text = f"INTERVIEW SCORECARD — {interviewer}\n\n"
    for competency, rating in ratings.items():
        scorecard_text += f"{competency}: {rating}/5\n"
    avg = sum(ratings.values()) / len(ratings) if ratings else 0
    scorecard_text += f"\nOverall: {avg:.1f}/5\nDecision: {decision}\n\nNotes:\n{notes}"
    try:
        existing_notes = req.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}",
            headers=AT_HEADERS).json().get("fields", {}).get("Notes", "")
        new_notes = (existing_notes + "\n\n" if existing_notes else "") + scorecard_text
        ats.update_candidate(record_id, {
            "Notes": new_notes,
            "Status": "Hired" if decision == "Hire" else ("Rejected" if decision == "No Hire" else None)
        })
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── OFFER TRACKING ────────────────────────────────────────────────────────────

@app.route("/ats/api/send-offer", methods=["POST"])
@login_required
def api_send_offer():
    data = request.json or {}
    try:
        from offer_letter import email_offer_letter
        cand = ats.get_candidate_by_email(data.get("email", ""))
        if not cand:
            return jsonify({"ok": False, "error": "Candidate not found"}), 404
        f = cand["fields"]
        email_offer_letter(f.get("Name",""), data["email"], f.get("Job_Title",""),
                          data.get("rate","TBD"), data.get("start_date","TBD"))
        ats.update_candidate(cand["id"], {"Status": "Final_Round",
                                           "Notes": f"Offer sent: {data.get('rate')} starting {data.get('start_date')}"})
        from jenny.notifications import notify_offer_sent
        notify_offer_sent(f.get("Name",""), f.get("Job_Title",""), data.get("rate","TBD"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── PUBLIC APPLY FORM ─────────────────────────────────────────────────────────

@app.route("/apply/<job_id>")
def apply_page(job_id):
    jobs    = ats.get_active_jobs()
    job_obj = next((j for j in jobs if j["fields"].get("Job_ID") == job_id), None)
    if not job_obj:
        return "Job not found or no longer accepting applications.", 404
    job = _map_job(job_obj)
    return render_template("apply.html", job=job, company_name=COMPANY_NAME,
                           jenny_name="Jenny")


@app.route("/apply/submit", methods=["POST"])
def apply_submit():
    import threading
    first = request.form.get("first_name", "").strip()
    last  = request.form.get("last_name", "").strip()
    name  = f"{first} {last}".strip()
    email_addr = request.form.get("email", "").strip()
    phone      = request.form.get("phone", "").strip()
    job_title  = request.form.get("job_title", "")
    job_id     = request.form.get("job_id", "")
    cover      = request.form.get("cover_note", "")
    linkedin   = request.form.get("linkedin", "")
    resume_file = request.files.get("resume")

    resume_text = ""
    if resume_file and resume_file.filename:
        import tempfile, os as _os
        suffix = _os.path.splitext(resume_file.filename)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            resume_file.save(tmp.name)
            try:
                from resume_parser import parse_resume
                resume_text = parse_resume(tmp.name)
            except:
                resume_text = cover
            _os.unlink(tmp.name)

    def process():
        try:
            notes = f"Cover note: {cover}\nLinkedIn: {linkedin}" if cover or linkedin else ""
            rec = ats.create_candidate(name, email_addr, phone, job_title, job_id,
                                       source="Direct Apply", notes=notes)
            record_id = rec["id"]

            from jenny.notifications import notify_new_application
            notify_new_application(name, job_title, "Direct Apply")

            if resume_text:
                from candidate_scorer import score_candidate_from_resume
                from jenny.notifications import notify_qualified_candidate
                jobs_list = ats.get_active_jobs()
                job_obj   = next((j for j in jobs_list if j["fields"].get("Job_ID") == job_id), {})
                job_desc  = job_obj.get("fields", {}).get("Description", "")
                job_req   = job_obj.get("fields", {}).get("Requirements", "")
                score_data = score_candidate_from_resume(resume_text, name, job_title, job_desc, job_req)
                score = score_data.get("score", 0)
                ats.update_candidate_after_call(
                    record_id, "resume-screen", score,
                    score_data.get("summary",""), "\n".join(score_data.get("strengths",[])),
                    "\n".join(score_data.get("concerns",[])),
                    score_data.get("comp_expectation",""), score_data.get("availability",""),
                    score_data.get("recommend",""), resume_text
                )
                if score >= 7:
                    email_out.send_qualified_email(name, email_addr, job_title, score_data.get("summary",""))
                    notify_qualified_candidate(name, job_title, score, score_data.get("comp_expectation",""))
                elif score <= 4:
                    email_out.send_rejection_email(name, email_addr, job_title)
            else:
                email_out.send_application_received_email(name, email_addr, job_title)
        except Exception as ex:
            print(f"[APPLY] Error processing {name}: {ex}")

    threading.Thread(target=process, daemon=True).start()
    return jsonify({"ok": True})


# ── CANDIDATE PORTAL ──────────────────────────────────────────────────────────

@app.route("/portal", methods=["GET", "POST"])
def candidate_portal():
    candidate = None
    error     = None
    hiring_manager = os.getenv("YOUR_NAME", "the hiring team")
    if request.method == "POST":
        email_addr = request.form.get("email", "").strip()
        phone      = request.form.get("phone", "").strip().replace(" ","").replace("-","").replace("(","").replace(")","")
        found      = ats.get_candidate_by_email(email_addr)
        if found:
            stored_phone = (found.get("fields", {}).get("Phone") or "").replace(" ","").replace("-","").replace("(","").replace(")","")
            if phone and stored_phone and not stored_phone.endswith(phone[-4:]):
                error = "Phone number doesn't match our records."
            else:
                candidate = _map_candidate(found)
        else:
            error = "No application found with that email address."
    return render_template("candidate_portal.html", candidate=candidate, error=error,
                           company_name=COMPANY_NAME, hiring_manager=hiring_manager)


# ── JENNY ROUTES ──────────────────────────────────────────────────────────────

@app.route("/jenny/async-interview/<record_id>")
def jenny_async_interview(record_id):
    resp = req.get(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_CANDIDATES}/{record_id}",
        headers=AT_HEADERS)
    if resp.status_code != 200:
        return "Interview link not found.", 404
    f = resp.json().get("fields", {})
    from jenny.async_video import get_async_interview_page
    html = get_async_interview_page(f.get("Name","Candidate"), f.get("Job_Title","Role"), record_id)
    from flask import make_response
    return make_response(html, 200, {"Content-Type": "text/html"})


@app.route("/jenny/submit-video-interview", methods=["POST"])
def jenny_submit_video():
    import threading
    record_id = request.form.get("record_id","")
    job_title = request.form.get("job_title","")
    questions = [request.form.get(f"question_{i}","") for i in range(10)
                 if request.form.get(f"question_{i}")]

    def process():
        try:
            transcripts = []
            for i, q in enumerate(questions):
                video = request.files.get(f"video_{i}")
                if video:
                    transcripts.append(f"[Video response to: {q}]")

            if transcripts:
                from jenny.async_video import evaluate_video_responses
                score_data = evaluate_video_responses(questions, transcripts, job_title)
                score = score_data.get("score", 0)
                ats.update_candidate_after_call(
                    record_id, "async-video", score,
                    score_data.get("summary",""), "\n".join(score_data.get("strengths",[])),
                    "\n".join(score_data.get("concerns",[])), "", "", score_data.get("recommend",""),
                    "\n\n".join(f"Q: {q}\nA: {t}" for q, t in zip(questions, transcripts))
                )
        except Exception as ex:
            print(f"[JENNY VIDEO] Error: {ex}")

    threading.Thread(target=process, daemon=True).start()
    return jsonify({"ok": True})


# ── PWA MANIFEST ──────────────────────────────────────────────────────────────

@app.route("/manifest.json")
def pwa_manifest():
    return jsonify({
        "name": COMPANY_NAME + " Hiring",
        "short_name": "Hiring",
        "start_url": "/ats/",
        "display": "standalone",
        "background_color": "#0f1e3d",
        "theme_color": "#0f1e3d",
        "icons": [
            {"src": "/ats/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/ats/static/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })


# ── REDIRECT ROOT ─────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return redirect("/ats/")


if __name__ == "__main__":
    print(f"\n  {COMPANY_NAME} — Hiring Dashboard")
    print("  Open: http://localhost:5057\n")
    app.run(host="0.0.0.0", port=5057, debug=False)
