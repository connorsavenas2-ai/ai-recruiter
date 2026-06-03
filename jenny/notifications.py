"""
Discord & Slack notifications — Jenny pings you when something important happens.
"""

import os
import requests
from jenny.persona import JENNY_NAME, COMPANY_NAME

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK_URL", "")


def _discord(message: str, color: int = 0x2563eb, fields: list = None):
    if not DISCORD_WEBHOOK:
        return
    embed = {"description": message, "color": color}
    if fields:
        embed["fields"] = [{"name": f["name"], "value": f["value"], "inline": True}
                           for f in fields]
    requests.post(DISCORD_WEBHOOK, json={
        "username": f"{JENNY_NAME} | {COMPANY_NAME}",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=jenny",
        "embeds": [embed]
    }, timeout=5)


def _slack(message: str, blocks: list = None):
    if not SLACK_WEBHOOK:
        return
    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks
    requests.post(SLACK_WEBHOOK, json=payload, timeout=5)


def _notify(message: str, color: int = 0x2563eb, fields: list = None):
    _discord(message, color, fields)
    _slack(message)


def notify_new_application(name: str, job: str, source: str, score: int = 0):
    color = 0x16a34a if score >= 7 else (0xca8a04 if score >= 5 else 0x6b7a99)
    _notify(
        f"📥 **New Application** — {name} for **{job}** via {source}" +
        (f" — Score: **{score}/10** 🔥" if score >= 7 else ""),
        color=color,
        fields=[{"name": "Candidate", "value": name},
                {"name": "Role", "value": job},
                {"name": "Source", "value": source},
                {"name": "AI Score", "value": f"{score}/10" if score else "Pending"}]
    )


def notify_qualified_candidate(name: str, job: str, score: int, comp: str):
    _notify(
        f"⭐ **Qualified Candidate!** — {name} scored **{score}/10** for {job}. Calendly link sent.",
        color=0x16a34a,
        fields=[{"name": "Candidate", "value": name},
                {"name": "Score", "value": f"{score}/10"},
                {"name": "Comp Expectation", "value": comp or "Not stated"}]
    )


def notify_interview_booked(name: str, job: str, datetime_str: str):
    _notify(
        f"📅 **Interview Booked!** — {name} booked a final interview for {job} on {datetime_str}.",
        color=0x7c3aed,
        fields=[{"name": "Candidate", "value": name},
                {"name": "Role", "value": job},
                {"name": "When", "value": datetime_str}]
    )


def notify_offer_sent(name: str, job: str, rate: str):
    _notify(
        f"📝 **Offer Sent!** — Offer letter sent to {name} for {job} at {rate}.",
        color=0x059669,
        fields=[{"name": "Candidate", "value": name},
                {"name": "Role", "value": job},
                {"name": "Rate", "value": rate}]
    )


def notify_hired(name: str, job: str):
    _notify(
        f"🎉 **Hired!** — {name} accepted the offer for {job}. Welcome to the team!",
        color=0x065f46,
        fields=[{"name": "New Hire", "value": name}, {"name": "Role", "value": job}]
    )


def notify_jenny_call_complete(name: str, job: str, score: int, recommend: str):
    color = 0x16a34a if score >= 7 else (0xca8a04 if score >= 5 else 0xdc2626)
    emoji = "✅" if score >= 7 else ("🟡" if score >= 5 else "❌")
    _notify(
        f"{emoji} **Jenny's Call Complete** — {name} | {job} | Score: **{score}/10** | {recommend}",
        color=color,
        fields=[{"name": "Candidate", "value": name},
                {"name": "Score", "value": f"{score}/10"},
                {"name": "Recommendation", "value": recommend}]
    )
