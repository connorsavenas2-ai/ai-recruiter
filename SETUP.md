# AI Recruiter — Setup Guide

Full automation: AI phone screens → scoring → scheduling → you only join the final round.

---

## Step 1 — Get API Keys (do these in order)

### 1. Anthropic (Claude) — 5 min
- Go to: https://console.anthropic.com/settings/keys
- Create key → paste into .env as ANTHROPIC_API_KEY

### 2. Bland.ai (AI Voice Calls) — 10 min
- Sign up: https://app.bland.ai
- Dashboard → API Keys → copy key → paste as BLAND_API_KEY
- **Clone your voice:**
  - Go to Voices → Clone Voice
  - Record 10 minutes of yourself speaking naturally (read articles, talk about anything)
  - Copy the Voice ID → paste as BLAND_VOICE_ID
  - The AI will screen candidates using your voice clone

### 3. Airtable (Candidate Database) — 15 min
- Sign up: https://airtable.com (free plan works)
- Create a new Base called "AI Recruiter ATS"
- Create 3 tables with these EXACT names:
  - **Candidates** — add all fields listed in airtable_ats.py comments
  - **Jobs** — add all fields listed
  - **Call_Logs** — add all fields listed
- Get your API key: https://airtable.com/create/tokens
- Get your Base ID from the URL: airtable.com/appXXXXXXXXXXXXXX
- Paste both into .env

### 4. Google Calendar — 15 min
- Go to: https://console.cloud.google.com
- Create a new project → Enable "Google Calendar API"
- Credentials → Create Credentials → OAuth 2.0 → Desktop App
- Download credentials JSON → save as credentials.json in this folder
- First time you run calendar commands, a browser window will open to authorize

### 5. Calendly — 5 min
- Go to: https://calendly.com/integrations/api_webhooks
- Generate API Key → paste as CALENDLY_API_KEY
- Get your user URI: https://api.calendly.com/users/me (use your API key as Bearer token)
- Create a new event type called "Final Interview — 30 min"
- Paste your booking link as CALENDLY_BOOKING_LINK
- Make sure Calendly is connected to your Google Calendar (Settings → Calendar Sync)

### 6. Gmail App Password — 3 min
- Go to: https://myaccount.google.com/security
- 2-Step Verification must be ON
- App Passwords → Generate → select Mail → copy 16-char password
- Paste as GMAIL_APP_PASSWORD

### 7. Twilio (SMS) — 10 min
- Sign up: https://console.twilio.com
- Get a phone number (free trial gives you one)
- Copy Account SID, Auth Token, and phone number into .env

### 8. Apollo.io (Candidate Sourcing) — 5 min
- Sign up: https://app.apollo.io (free tier: 50 exports/month)
- Settings → Integrations → API → copy key → paste as APOLLO_API_KEY

---

## Step 2 — Install & Configure

```bash
cd /Users/connorsavenas/ai-recruiter

# Copy env template
cp .env.template .env

# Fill in all values
nano .env   (or open in VS Code)

# Install dependencies
pip3 install -r requirements.txt
```

---

## Step 3 — First Run

```bash
# Run setup (creates Calendly webhook + Bland.ai inbound agent)
python main.py setup

# Add your first job
python main.py add-job

# Start the webhook server
python webhook_server.py
# In a NEW terminal window:
brew install ngrok    # if not installed
ngrok http 5055
# Copy the https URL (e.g. https://abc123.ngrok.io)
# Paste it as WEBHOOK_BASE_URL in .env
```

---

## Step 4 — Connect Job Boards via Zapier (free tier works)

Go to https://zapier.com and create these Zaps:

### Indeed Zap:
- Trigger: Indeed → New Job Application
- Action: Webhooks by Zapier → POST
  - URL: https://YOUR-NGROK-URL.ngrok.io/webhooks/application
  - Payload: name, email, phone, job_title, source="Indeed"

### LinkedIn Zap (if using LinkedIn Jobs):
- Same setup, source="LinkedIn"

### Handshake:
- Same setup, source="Handshake"

---

## Daily Operations (what you do = nothing)

The system handles:
1. New application comes in → webhook fires
2. Candidate gets SMS "we received your application"
3. AI calls them within minutes for 10-min phone screen
4. Claude scores 1-10 based on transcript
5. Score ≥ 7 → candidate gets email + SMS with your Calendly link
6. Score < 5 → candidate gets polite rejection email
7. They book via Calendly → Google Calendar updated + confirmation email
8. You get notified of your final interview

You only do: **show up for final round interviews with pre-screened, qualified candidates.**

---

## Commands Reference

```bash
python main.py add-job              # Add a new job opening
python main.py jobs                 # List active jobs
python main.py candidates           # View ranked qualified candidates
python main.py digest               # Get Claude's weekly summary
python main.py call +15551234567    # Manually trigger a screening call
python main.py recent-calls         # See recent AI calls
python main.py source               # Find candidates on Apollo.io
python main.py sourcing-strategy    # Claude recommends where to find candidates
python main.py upcoming             # Upcoming interviews on calendar
python main.py available-slots      # Your open interview slots
python main.py setup                # First-time setup
python main.py server               # Start webhook server
```

---

## Cost Breakdown (monthly estimate)

| Service | Cost | What It Does |
|---------|------|-------------|
| Bland.ai | ~$50-150 | AI phone screens |
| Airtable | Free | Candidate database |
| Twilio | ~$10-20 | SMS to candidates |
| Apollo.io | Free-$49 | Finding candidates |
| Anthropic | ~$10-30 | Scoring + emails |
| Calendly | Free | Scheduling |
| Google Calendar | Free | Calendar sync |
| Gmail | Free | Outreach emails |
| Zapier | Free | Board connectors |
| **Total** | **~$70-250/mo** | Full automation |

---

## Legal Notes

- Bland.ai calls disclose AI at the start — required in many states
- SMS requires opt-in consent — the application itself is considered consent when disclosed
- LinkedIn/Indeed automation is via Zapier only (official integrations, not scraping)
- All 1099 and internship roles are clearly labeled in all communications
