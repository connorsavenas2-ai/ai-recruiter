"""
Auto-posts jobs to Indeed, LinkedIn, and Handshake using browser-use.
Leverages the existing browser-use-local setup on your machine.

Usage:
  python job_poster.py --job-id JOB-XXXX --boards indeed linkedin
"""

import asyncio
import sys
import argparse
from pathlib import Path
import airtable_ats as ats

BROWSER_USE_DIR = Path("/Users/connorsavenas/browser-use-local")
sys.path.insert(0, str(BROWSER_USE_DIR))


async def _run_browser_task(task: str) -> str:
    """Run a browser-use task using the existing browser-use-local setup."""
    import os
    from dotenv import load_dotenv
    load_dotenv(BROWSER_USE_DIR / ".env")

    from browser_use import Agent, BrowserProfile, BrowserSession, ChatGoogle, ChatOpenAI

    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        from browser_use import ChatGoogle
        llm = ChatGoogle(model="gemini-2.5-flash", api_key=google_key)
    else:
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "")
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key, base_url=openai_base or None)

    browser = BrowserSession(
        browser_profile=BrowserProfile(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            user_data_dir=str(BROWSER_USE_DIR / "chrome-profile"),
            window_size={"width": 1280, "height": 900}
        )
    )
    agent = Agent(task=task, llm=llm, browser_session=browser)
    try:
        result = await agent.run()
        return str(result)
    finally:
        await browser.kill()


def _build_indeed_task(job: dict) -> str:
    f    = job["fields"]
    title = f.get("Job_Title", "")
    desc  = f.get("Description", "")
    reqs  = f.get("Requirements", "")
    pay   = f.get("Pay_Range", "Competitive")
    jtype = f.get("Type", "1099")

    return f"""
Go to indeed.com/hire and post a new job with these details:
- Job title: {title}
- Job type: Contract / 1099
- Pay: {pay}
- Location: Remote
- Description: {desc}

Requirements:
{reqs}

Note: This is a 1099 independent contractor position.
Complete the posting and confirm it was submitted successfully.
"""


def _build_linkedin_task(job: dict) -> str:
    f     = job["fields"]
    title = f.get("Job_Title", "")
    desc  = f.get("Description", "")
    reqs  = f.get("Requirements", "")
    pay   = f.get("Pay_Range", "")

    return f"""
Go to linkedin.com/talent/jobs/create and post a new job:
- Title: {title}
- Employment type: Contract
- Remote: Yes
- Description: {desc}
- Requirements: {reqs}
{f"- Compensation: {pay}" if pay else ""}

This is a 1099 contractor role. Complete the posting.
"""


def _build_handshake_task(job: dict) -> str:
    f     = job["fields"]
    title = f.get("Job_Title", "")
    desc  = f.get("Description", "")
    reqs  = f.get("Requirements", "")
    jtype = f.get("Type", "")

    return f"""
Go to app.joinhandshake.com and post a new job/internship:
- Title: {title}
- Type: {"Internship" if jtype == "Internship" else "Part-time / Contract"}
- Remote: Yes
- Description: {desc}
- Requirements: {reqs}

Complete the posting and confirm submission.
"""


BOARD_TASKS = {
    "indeed":    _build_indeed_task,
    "linkedin":  _build_linkedin_task,
    "handshake": _build_handshake_task
}


def post_job(job_id: str, boards: list[str]) -> dict:
    """Post a job from Airtable to the specified job boards."""
    active_jobs = ats.get_active_jobs()
    job         = next((j for j in active_jobs if j["fields"].get("Job_ID") == job_id), None)
    if not job:
        raise ValueError(f"Job {job_id} not found or not active")

    results = {}
    for board in boards:
        if board not in BOARD_TASKS:
            print(f"  Unknown board: {board}")
            continue

        task = BOARD_TASKS[board](job)
        print(f"  Posting to {board}...")
        try:
            result = asyncio.run(_run_browser_task(task))
            results[board] = {"success": True, "result": result[:200]}
            print(f"  ✓ {board}: posted")
        except Exception as e:
            results[board] = {"success": False, "error": str(e)}
            print(f"  ✗ {board}: {e}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-post job to job boards")
    parser.add_argument("--job-id",  required=True, help="Airtable job ID (JOB-XXXX)")
    parser.add_argument("--boards",  nargs="+",
                        default=["indeed", "linkedin"],
                        choices=["indeed", "linkedin", "handshake"],
                        help="Which boards to post to")
    args = parser.parse_args()
    post_job(args.job_id, args.boards)
