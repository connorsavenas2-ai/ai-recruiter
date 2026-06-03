"""
Multi-step outreach sequences — 3-email drip that auto-stops on reply.
Day 1: Initial outreach
Day 3: Follow-up (if no reply)
Day 7: Final nudge (if no reply)

State is tracked in a local SQLite DB so it survives restarts.
Run the scheduler daily: python email_sequences.py run
Or integrate into the main scheduler.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from config import get_ai_client, YOUR_NAME, COMPANY_NAME, CALENDLY_BOOKING_LINK
from email_outreach import _send

DB_PATH = Path(__file__).parent / "sequences.db"

SEQUENCE_DELAYS = [0, 3, 7]  # days after enrollment


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_email TEXT NOT NULL,
            candidate_name  TEXT NOT NULL,
            job_title       TEXT NOT NULL,
            job_description TEXT DEFAULT '',
            step            INTEGER DEFAULT 0,
            enrolled_at     TEXT NOT NULL,
            next_send_at    TEXT NOT NULL,
            stopped         INTEGER DEFAULT 0,
            stop_reason     TEXT DEFAULT '',
            airtable_id     TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def enroll(candidate_email: str, candidate_name: str, job_title: str,
           job_description: str = "", airtable_id: str = "") -> int:
    """Add a candidate to a 3-step outreach sequence."""
    conn = _db()
    # Don't double-enroll
    existing = conn.execute(
        "SELECT id FROM sequences WHERE candidate_email=? AND job_title=? AND stopped=0",
        (candidate_email, job_title)
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]

    now      = datetime.utcnow()
    next_at  = now.isoformat()
    row_id   = conn.execute(
        "INSERT INTO sequences (candidate_email,candidate_name,job_title,job_description,"
        "step,enrolled_at,next_send_at,stopped,airtable_id) VALUES (?,?,?,?,0,?,?,0,?)",
        (candidate_email, candidate_name, job_title, job_description,
         now.isoformat(), next_at, airtable_id)
    ).lastrowid
    conn.commit()
    conn.close()
    return row_id


def stop(candidate_email: str, job_title: str = "", reason: str = "replied") -> None:
    """Stop sequences for a candidate — call this when they reply."""
    conn = _db()
    if job_title:
        conn.execute(
            "UPDATE sequences SET stopped=1, stop_reason=? WHERE candidate_email=? AND job_title=?",
            (reason, candidate_email, job_title)
        )
    else:
        conn.execute(
            "UPDATE sequences SET stopped=1, stop_reason=? WHERE candidate_email=?",
            (reason, candidate_email)
        )
    conn.commit()
    conn.close()


def _build_sequence_email(step: int, candidate_name: str, job_title: str,
                          job_description: str) -> dict:
    client, model = get_ai_client()

    contexts = [
        f"This is the first outreach. Introduce the {job_title} opportunity warmly and ask if they're interested.",
        f"This is a gentle follow-up (3 days after first email). Reference the previous email briefly. Keep it very short — 2-3 lines max.",
        f"This is the final follow-up (7 days). Very brief. Make it easy for them to say yes or no."
    ]

    prompt = f"""Write a cold recruiting email for step {step+1} of 3.

Sender: {YOUR_NAME} at {COMPANY_NAME}
Candidate: {candidate_name}
Job: {job_title}
Description: {job_description or "1099 contractor finance/business role"}
Context: {contexts[step]}
Calendly link: {CALENDLY_BOOKING_LINK}

Rules:
- Be human and direct, not corporate
- Step 1: ~100 words. Step 2: ~40 words. Step 3: ~25 words.
- Never say "I hope this email finds you well"
- Step 3 subject should be like "Should I close your file?"

Return ONLY valid JSON:
{{"subject": "...", "body_html": "...", "body_text": "..."}}"""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.5
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_due_sequences() -> int:
    """Send all emails that are due right now. Returns count sent."""
    conn  = _db()
    now   = datetime.utcnow().isoformat()
    due   = conn.execute(
        "SELECT * FROM sequences WHERE stopped=0 AND next_send_at <= ? AND step < 3",
        (now,)
    ).fetchall()

    sent = 0
    for row in due:
        try:
            email_data = _build_sequence_email(
                row["step"], row["candidate_name"],
                row["job_title"], row["job_description"]
            )
            _send(row["candidate_email"], email_data["subject"],
                  email_data["body_html"], email_data["body_text"])

            next_step = row["step"] + 1
            if next_step >= 3:
                # Sequence complete
                conn.execute(
                    "UPDATE sequences SET step=?, stopped=1, stop_reason='completed' WHERE id=?",
                    (next_step, row["id"])
                )
            else:
                delay_days = SEQUENCE_DELAYS[next_step] - SEQUENCE_DELAYS[row["step"]]
                next_at    = (datetime.utcnow() + timedelta(days=delay_days)).isoformat()
                conn.execute(
                    "UPDATE sequences SET step=?, next_send_at=? WHERE id=?",
                    (next_step, next_at, row["id"])
                )
            conn.commit()
            sent += 1
            print(f"  [SEQ] Sent step {row['step']+1}/3 to {row['candidate_name']} ({row['candidate_email']})")
        except Exception as e:
            print(f"  [SEQ ERROR] {row['candidate_email']}: {e}")

    conn.close()
    return sent


def get_sequence_stats() -> dict:
    conn   = _db()
    total  = conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM sequences WHERE stopped=0").fetchone()[0]
    done   = conn.execute("SELECT COUNT(*) FROM sequences WHERE stop_reason='completed'").fetchone()[0]
    replied = conn.execute("SELECT COUNT(*) FROM sequences WHERE stop_reason='replied'").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "completed": done, "replied": replied}


if __name__ == "__main__":
    import sys
    if "run" in sys.argv:
        n = run_due_sequences()
        print(f"Sent {n} emails.")
    elif "stats" in sys.argv:
        print(get_sequence_stats())
    else:
        print("Usage: python email_sequences.py [run|stats]")
