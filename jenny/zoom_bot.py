"""
Jenny's Zoom/Teams/Google Meet interview bot via Recall.ai.
Jenny joins the meeting as a participant, conducts the interview,
transcribes it, and scores the candidate automatically.

Sign up at: https://www.recall.ai — free trial available.
Docs: https://docs.recall.ai

Usage:
  jenny_bot = JennyZoomBot()
  bot_id = jenny_bot.join_meeting("https://zoom.us/j/123456789", candidate_name, job_title)
  # Later, after meeting ends:
  result = jenny_bot.get_interview_result(bot_id)
"""

import os
import requests
import json
from jenny.persona import get_interview_script, JENNY_NAME, JENNY_FULL_NAME
from config import get_ai_client

RECALL_API_KEY = os.getenv("RECALL_API_KEY", "")
RECALL_BASE    = "https://us-east-1.recall.ai/api/v1"
RECALL_HEADERS = {
    "Authorization": f"Token {RECALL_API_KEY}",
    "Content-Type": "application/json"
}

# Default interview questions by role type
QUESTION_BANK = {
    "finance": [
        "Walk me through your most relevant finance or accounting experience.",
        "Describe a time you found an error or discrepancy in financial data. How did you handle it?",
        "What financial modeling or reporting tools do you use regularly?",
        "How do you prioritize when managing multiple deadlines?",
        "What's your experience with 1099 / contract work?",
    ],
    "marketing": [
        "Tell me about a marketing campaign you ran and the results you drove.",
        "How do you measure the success of a content or social media strategy?",
        "What tools do you use for analytics and reporting?",
        "Describe your experience with paid vs. organic growth.",
        "What draws you to contract/freelance work?",
    ],
    "operations": [
        "Describe a process you improved and how you measured the impact.",
        "Tell me about a time you had to coordinate across multiple teams.",
        "What project management tools do you use?",
        "How do you handle shifting priorities mid-project?",
        "What's your availability and preferred working style?",
    ],
    "sales": [
        "Walk me through your sales process from prospecting to close.",
        "What's the largest deal you've closed, and how did you get there?",
        "How do you handle rejection or a cold prospect?",
        "What CRM tools have you used?",
        "Are you comfortable with performance-based / commission compensation?",
    ],
    "default": [
        "Tell me about yourself and what you're looking for in your next role.",
        "What experience do you have that's most relevant to this position?",
        "Describe a challenge you faced at work and how you solved it.",
        "What does your ideal working arrangement look like?",
        "Do you have any questions about the role or our company?",
    ]
}


def get_questions_for_job(job_title: str) -> list[str]:
    title_lower = job_title.lower()
    for key in QUESTION_BANK:
        if key in title_lower:
            return QUESTION_BANK[key]
    return QUESTION_BANK["default"]


class JennyZoomBot:
    def join_meeting(
        self,
        meeting_url: str,
        candidate_name: str,
        job_title: str,
        candidate_email: str = "",
        airtable_record_id: str = "",
        custom_questions: list[str] | None = None,
        webhook_url: str = ""
    ) -> str:
        """
        Deploy Jenny as a bot into a Zoom/Teams/Meet meeting.
        Returns the bot_id — save this to fetch results later.
        """
        questions = custom_questions or get_questions_for_job(job_title)
        script    = get_interview_script(job_title, questions)

        payload = {
            "meeting_url": meeting_url,
            "bot_name":    f"{JENNY_NAME} | Recruiting Assistant",
            "transcription_options": {"provider": "assembly_ai"},
            "recording_mode": "speaker_view",
            "real_time_transcription": {
                "partial_results": False,
                "destination_url": webhook_url or os.getenv("WEBHOOK_BASE_URL", "") + "/webhooks/jenny/transcript"
            },
            "automatic_leave": {
                "waiting_room_timeout": 600,
                "noone_joined_timeout": 300,
                "everyone_left_timeout": 60
            },
            "metadata": {
                "candidate_name":    candidate_name,
                "candidate_email":   candidate_email,
                "job_title":         job_title,
                "airtable_record_id": airtable_record_id,
                "interview_questions": json.dumps(questions)
            },
            # Chat message Jenny sends when she joins
            "chat": {
                "on_bot_join": {
                    "send_to": "everyone",
                    "message": f"Hi {candidate_name.split()[0]}! I'm {JENNY_FULL_NAME}, an AI recruiting assistant for {os.getenv('COMPANY_NAME', 'our company')}. I'll be conducting your first-round interview today. We'll go through about 5 questions — takes around 20-25 minutes. Feel free to ask me anything! Let's get started. 🎙️"
                }
            }
        }

        if not RECALL_API_KEY:
            print("[JENNY] RECALL_API_KEY not set — bot not deployed (simulation mode)")
            return "sim-bot-id-123"

        resp = requests.post(f"{RECALL_BASE}/bot", headers=RECALL_HEADERS, json=payload)
        resp.raise_for_status()
        bot_id = resp.json().get("id", "")
        print(f"[JENNY] Bot deployed to meeting. Bot ID: {bot_id}")
        return bot_id

    def get_bot_status(self, bot_id: str) -> dict:
        resp = requests.get(f"{RECALL_BASE}/bot/{bot_id}", headers=RECALL_HEADERS)
        resp.raise_for_status()
        return resp.json()

    def get_transcript(self, bot_id: str) -> str:
        resp = requests.get(f"{RECALL_BASE}/bot/{bot_id}/transcript", headers=RECALL_HEADERS)
        resp.raise_for_status()
        words = resp.json()
        lines = []
        current_speaker = None
        current_text    = []
        for word in words:
            speaker = word.get("speaker", "Unknown")
            if speaker != current_speaker:
                if current_text:
                    lines.append(f"{current_speaker}: {' '.join(current_text)}")
                current_speaker = speaker
                current_text    = [word.get("text", "")]
            else:
                current_text.append(word.get("text", ""))
        if current_text:
            lines.append(f"{current_speaker}: {' '.join(current_text)}")
        return "\n".join(lines)

    def get_recording_url(self, bot_id: str) -> str:
        data = self.get_bot_status(bot_id)
        return data.get("video_url", "") or data.get("recording_url", "")

    def get_interview_result(self, bot_id: str, job_title: str, job_description: str = "") -> dict:
        """Get transcript + score after interview ends."""
        from candidate_scorer import score_candidate_from_transcript
        transcript   = self.get_transcript(bot_id)
        recording    = self.get_recording_url(bot_id)
        score_data   = score_candidate_from_transcript(transcript, job_title, job_description, "")
        return {
            "bot_id":      bot_id,
            "transcript":  transcript,
            "recording":   recording,
            "score_data":  score_data
        }

    def list_recent_bots(self, limit: int = 20) -> list:
        resp = requests.get(f"{RECALL_BASE}/bot?limit={limit}", headers=RECALL_HEADERS)
        resp.raise_for_status()
        return resp.json().get("results", [])


jenny_bot = JennyZoomBot()
