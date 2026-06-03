"""
Candidate scoring — uses free AI models (Groq/Cerebras/OpenRouter).
No Anthropic API key needed.
"""

import json
from config import get_ai_client


def _chat(prompt: str, max_tokens: int = 1000) -> str:
    client, model = get_ai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def score_candidate_from_resume(
    resume_text: str,
    candidate_name: str,
    job_title: str,
    job_description: str,
    job_requirements: str
) -> dict:
    prompt = f"""You are a recruiting analyst. Score this candidate 1-10 for the job.

JOB: {job_title}
DESCRIPTION: {job_description or "Finance/business/operations role"}
REQUIREMENTS: {job_requirements or "Relevant experience and skills"}

CANDIDATE: {candidate_name}
RESUME:
{resume_text[:3500]}

Return ONLY valid JSON, no markdown:
{{
  "score": <1-10>,
  "recommend": "<Strong Yes|Yes|Maybe|No>",
  "summary": "<2-3 sentences>",
  "strengths": ["strength 1", "strength 2"],
  "concerns": ["concern 1"],
  "comp_expectation": "<if mentioned, else Unknown>",
  "availability": "<if mentioned, else Unknown>",
  "next_step": "<Send Calendly|Request More Info|Reject>",
  "interview_questions": ["q1 for final round", "q2"]
}}

9-10=exceptional, 7-8=good, 5-6=partial, 1-4=poor"""

    return json.loads(_chat(prompt))


def score_candidate_from_transcript(
    transcript: str,
    job_title: str,
    job_description: str,
    job_requirements: str
) -> dict:
    prompt = f"""You are a recruiting analyst. Score this candidate 1-10 based on their phone screen.

JOB: {job_title}
DESCRIPTION: {job_description}
REQUIREMENTS: {job_requirements}

TRANSCRIPT:
{transcript[:3500]}

Return ONLY valid JSON, no markdown:
{{
  "score": <1-10>,
  "recommend": "<Strong Yes|Yes|Maybe|No>",
  "summary": "<2-3 sentences>",
  "strengths": ["strength 1", "strength 2"],
  "concerns": ["concern 1"],
  "comp_expectation": "<what they said or Unknown>",
  "availability": "<when they can start>",
  "next_step": "<Send Calendly|Request More Info|Reject>",
  "interview_questions": ["q1", "q2"]
}}"""

    return json.loads(_chat(prompt))


def rank_candidates_for_job(candidates: list, job_title: str) -> list:
    scored = []
    for c in candidates:
        f = c.get("fields", {})
        scored.append({
            "record_id":       c["id"],
            "name":            f.get("Name", "Unknown"),
            "score":           f.get("Score", 0),
            "recommend":       f.get("Recommend", ""),
            "comp":            f.get("Comp_Expectation", ""),
            "availability":    f.get("Availability", ""),
            "summary":         f.get("Score_Summary", ""),
            "calendly_booked": f.get("Calendly_Booked", False),
            "email":           f.get("Email", ""),
            "phone":           f.get("Phone", "")
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, c in enumerate(scored):
        c["rank"] = i + 1
    return scored


def generate_weekly_digest(candidates: list, job_title: str = "All Roles") -> str:
    data = json.dumps([{
        "name":      c.get("name"),
        "score":     c.get("score"),
        "recommend": c.get("recommend"),
        "comp":      c.get("comp"),
        "summary":   c.get("summary", "")[:150]
    } for c in candidates[:15]], indent=2)

    prompt = f"""Write a concise weekly recruiting digest for Connor (the hiring manager).

Role focus: {job_title}
Candidates: {data}

Include:
1. Pipeline summary (X applied, Y screened, Z qualified)
2. Top 3 candidates with name, score, one-line why
3. Anyone who booked a final interview
4. Recommended actions this week

Max 250 words, bullet points, no fluff."""

    return _chat(prompt, max_tokens=500)


def source_candidates_via_ai(job_title: str, job_description: str) -> str:
    prompt = f"""You are a talent sourcing expert. Give specific sourcing strategies for:

Job: {job_title}
Description: {job_description}
Type: 1099 contractor or internship

Provide:
1. Top 5 Apollo.io/LinkedIn search job titles to look for
2. Top 3 subreddits or communities where this candidate hangs out
3. Best Indeed/Handshake search keywords
4. Sample cold email subject line (7 words max)
5. Best time to send outreach

Be specific."""

    return _chat(prompt, max_tokens=500)
