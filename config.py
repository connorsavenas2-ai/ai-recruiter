import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY     = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY          = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.getenv("OPENROUTER_API_KEY", "")
CEREBRAS_API_KEY      = os.getenv("CEREBRAS_API_KEY", "")
BLAND_API_KEY         = os.getenv("BLAND_API_KEY", "")
BLAND_VOICE_ID        = os.getenv("BLAND_VOICE_ID", "")
AIRTABLE_API_KEY      = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID      = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_CANDIDATES   = os.getenv("AIRTABLE_CANDIDATES_TABLE", "Candidates")
AIRTABLE_JOBS         = os.getenv("AIRTABLE_JOBS_TABLE", "Jobs")
AIRTABLE_CALLS        = os.getenv("AIRTABLE_CALLS_TABLE", "Call_Logs")
GOOGLE_CREDS_FILE     = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID", "primary")
CALENDLY_API_KEY      = os.getenv("CALENDLY_API_KEY", "")
CALENDLY_USER_URI     = os.getenv("CALENDLY_USER_URI", "")
CALENDLY_BOOKING_LINK = os.getenv("CALENDLY_BOOKING_LINK", "")
OUTREACH_EMAIL        = os.getenv("OUTREACH_EMAIL", "")
GMAIL_APP_PASSWORD    = os.getenv("GMAIL_APP_PASSWORD", "")
TWILIO_SID            = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN          = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE          = os.getenv("TWILIO_PHONE_NUMBER", "")
YOUR_NAME             = os.getenv("YOUR_NAME", "Connor")
COMPANY_NAME          = os.getenv("COMPANY_NAME", "Connor Savenas Ventures")
YOUR_EMAIL            = os.getenv("YOUR_EMAIL", "connorsavenas2@gmail.com")
WEBHOOK_BASE_URL      = os.getenv("WEBHOOK_BASE_URL", "http://localhost:5055")
APOLLO_API_KEY        = os.getenv("APOLLO_API_KEY", "")

# AI model selection — uses free models by default
# Priority: Groq (free+fast) → Cerebras (free) → OpenRouter free model → Anthropic (paid)
def get_ai_client():
    """Returns (client, model) using the best available free model."""
    from openai import OpenAI as _OpenAI

    if GROQ_API_KEY:
        return _OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1"), \
               "llama-3.3-70b-versatile"
    if CEREBRAS_API_KEY:
        return _OpenAI(api_key=CEREBRAS_API_KEY, base_url="https://api.cerebras.ai/v1"), \
               "llama3.3-70b"
    if OPENROUTER_API_KEY:
        return _OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1"), \
               "deepseek/deepseek-chat-v3-0324:free"
    if ANTHROPIC_API_KEY:
        import anthropic as _ant
        return _ant.Anthropic(api_key=ANTHROPIC_API_KEY), "claude-opus-4-8"
    raise RuntimeError("No AI API key found. Add GROQ_API_KEY to .env")

CLAUDE_MODEL = "llama-3.3-70b-versatile"  # default (Groq free)
