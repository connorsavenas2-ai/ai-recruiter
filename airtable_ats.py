"""
Airtable ATS — candidate database, job tracking, call logs.

Airtable base setup (create these tables manually at airtable.com):

TABLE: Candidates
  - Name (Single line text)
  - Email (Email)
  - Phone (Phone number)
  - Job_Title (Single line text)
  - Job_ID (Single line text)
  - Status (Single select): Applied, Called, Screened, Qualified, Final_Round, Hired, Rejected
  - Score (Number 1-10)
  - Score_Summary (Long text)
  - Strengths (Long text)
  - Concerns (Long text)
  - Comp_Expectation (Single line text)
  - Availability (Single line text)
  - Call_ID (Single line text)
  - Call_Recording_URL (URL)
  - Transcript (Long text)
  - Applied_Date (Date)
  - Called_Date (Date)
  - Source (Single line text): Indeed, LinkedIn, Handshake, Referral, Outreach
  - Notes (Long text)
  - Calendly_Booked (Checkbox)
  - Final_Interview_Date (Date)
  - Recommend (Single select): Strong Yes, Yes, Maybe, No

TABLE: Jobs
  - Job_Title (Single line text)
  - Job_ID (Single line text, formula: auto or manual)
  - Type (Single select): 1099, Internship, Part_Time
  - Description (Long text)
  - Requirements (Long text)
  - Pay_Range (Single line text)
  - Status (Single select): Active, Paused, Filled, Closed
  - Posted_Date (Date)
  - Applications_Count (Number)
  - Qualified_Count (Number)

TABLE: Call_Logs
  - Call_ID (Single line text)
  - Candidate_Name (Single line text)
  - Candidate_Email (Single line text)
  - Job_Title (Single line text)
  - Direction (Single select): Outbound, Inbound
  - Status (Single select): Completed, No_Answer, Voicemail, Failed
  - Duration_Seconds (Number)
  - Score (Number)
  - Recording_URL (URL)
  - Transcript (Long text)
  - Called_At (Date)
"""

import requests
from datetime import datetime
from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_CANDIDATES, AIRTABLE_JOBS, AIRTABLE_CALLS

BASE_URL = "https://api.airtable.com/v0"
HEADERS  = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}


def _url(table: str) -> str:
    return f"{BASE_URL}/{AIRTABLE_BASE_ID}/{table}"


def create_candidate(
    name: str,
    email: str,
    phone: str,
    job_title: str,
    job_id: str = "",
    source: str = "Unknown",
    notes: str = ""
) -> dict:
    payload = {"fields": {
        "Name": name,
        "Email": email,
        "Phone": phone,
        "Job_Title": job_title,
        "Job_ID": job_id,
        "Status": "Applied",
        "Source": source,
        "Applied_Date": datetime.now().strftime("%Y-%m-%d"),
        "Notes": notes
    }}
    resp = requests.post(_url(AIRTABLE_CANDIDATES), headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def update_candidate(record_id: str, fields: dict) -> dict:
    payload = {"fields": fields}
    resp = requests.patch(f"{_url(AIRTABLE_CANDIDATES)}/{record_id}", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def update_candidate_after_call(
    record_id: str,
    call_id: str,
    score: int,
    score_summary: str,
    strengths: str,
    concerns: str,
    comp_expectation: str,
    availability: str,
    recommend: str,
    transcript: str,
    recording_url: str = ""
) -> dict:
    status = "Qualified" if score >= 7 else "Screened"
    return update_candidate(record_id, {
        "Status": status,
        "Call_ID": call_id,
        "Score": score,
        "Score_Summary": score_summary,
        "Strengths": strengths,
        "Concerns": concerns,
        "Comp_Expectation": comp_expectation,
        "Availability": availability,
        "Recommend": recommend,
        "Transcript": transcript[:99000],  # Airtable long text limit
        "Call_Recording_URL": recording_url,
        "Called_Date": datetime.now().strftime("%Y-%m-%d")
    })


def get_candidate_by_email(email: str) -> dict | None:
    params = {"filterByFormula": f"{{Email}}='{email}'"}
    resp = requests.get(_url(AIRTABLE_CANDIDATES), headers=HEADERS, params=params)
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def get_qualified_candidates(job_id: str = "") -> list:
    formula = "{Score} >= 7"
    if job_id:
        formula = f"AND({formula}, {{Job_ID}}='{job_id}')"
    params = {
        "filterByFormula": formula,
        "sort[0][field]": "Score",
        "sort[0][direction]": "desc"
    }
    resp = requests.get(_url(AIRTABLE_CANDIDATES), headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("records", [])


def get_uncontacted_candidates(job_id: str = "") -> list:
    formula = "{Status}='Applied'"
    if job_id:
        formula = f"AND({formula}, {{Job_ID}}='{job_id}')"
    resp = requests.get(_url(AIRTABLE_CANDIDATES), headers=HEADERS, params={"filterByFormula": formula})
    resp.raise_for_status()
    return resp.json().get("records", [])


def create_job(
    title: str,
    job_type: str,
    description: str,
    requirements: str,
    pay_range: str = "TBD"
) -> dict:
    import uuid
    job_id = f"JOB-{str(uuid.uuid4())[:8].upper()}"
    payload = {"fields": {
        "Job_Title": title,
        "Job_ID": job_id,
        "Type": job_type,
        "Description": description,
        "Requirements": requirements,
        "Pay_Range": pay_range,
        "Status": "Active",
        "Posted_Date": datetime.now().strftime("%Y-%m-%d"),
        "Applications_Count": 0,
        "Qualified_Count": 0
    }}
    resp = requests.post(_url(AIRTABLE_JOBS), headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def get_active_jobs() -> list:
    params = {"filterByFormula": "{Status}='Active'"}
    resp = requests.get(_url(AIRTABLE_JOBS), headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("records", [])


def log_call(
    call_id: str,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    direction: str = "Outbound",
    status: str = "Completed",
    duration: int = 0,
    score: int = 0,
    recording_url: str = "",
    transcript: str = ""
) -> dict:
    payload = {"fields": {
        "Call_ID": call_id,
        "Candidate_Name": candidate_name,
        "Candidate_Email": candidate_email,
        "Job_Title": job_title,
        "Direction": direction,
        "Status": status,
        "Duration_Seconds": duration,
        "Score": score,
        "Recording_URL": recording_url,
        "Transcript": transcript[:99000],
        "Called_At": datetime.now().strftime("%Y-%m-%d")
    }}
    resp = requests.post(_url(AIRTABLE_CALLS), headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def mark_calendly_booked(record_id: str, interview_date: str = "") -> dict:
    fields = {"Calendly_Booked": True, "Status": "Final_Round"}
    if interview_date:
        fields["Final_Interview_Date"] = interview_date
    return update_candidate(record_id, fields)


def get_top_candidates_summary(job_id: str = "", limit: int = 10) -> str:
    candidates = get_qualified_candidates(job_id)[:limit]
    if not candidates:
        return "No qualified candidates found yet."
    lines = [f"TOP {len(candidates)} QUALIFIED CANDIDATES\n" + "="*40]
    for i, c in enumerate(candidates, 1):
        f = c.get("fields", {})
        lines.append(
            f"\n#{i} {f.get('Name', 'Unknown')} — Score: {f.get('Score', 'N/A')}/10\n"
            f"   Role: {f.get('Job_Title', '')}\n"
            f"   Comp: {f.get('Comp_Expectation', 'N/A')} | Available: {f.get('Availability', 'N/A')}\n"
            f"   Recommend: {f.get('Recommend', 'N/A')}\n"
            f"   Summary: {f.get('Score_Summary', '')[:150]}..."
        )
    return "\n".join(lines)
