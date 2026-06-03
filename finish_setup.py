#!/usr/bin/env python3
"""
AI Recruiter — Final Setup Wizard
Run this once: python finish_setup.py
It opens each website, waits for you to paste the key, tests it, and writes .env.
Takes ~15 minutes. After this, everything runs automatically forever.
"""

import os
import sys
import subprocess
import time
import webbrowser
import requests
import smtplib
from pathlib import Path
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent / ".env"
LAUNCHCTL = "/bin/launchctl"

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"

def p(msg):    print(msg)
def ok(msg):   print(f"{GREEN}  ✓ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}  ⚠ {msg}{RESET}")
def err(msg):  print(f"{RED}  ✗ {msg}{RESET}")
def head(msg): print(f"\n{BOLD}{CYAN}{'─'*50}\n  {msg}\n{'─'*50}{RESET}")
def ask(prompt, hide=False):
    import getpass
    return (getpass.getpass if hide else input)(f"{BLUE}  → {prompt}: {RESET}").strip()


def write_env(key, value):
    set_key(str(ENV_PATH), key, value)
    load_dotenv(ENV_PATH, override=True)


# ── STEP 1: AIRTABLE ─────────────────────────────────────────────────────────

def setup_airtable():
    head("STEP 1/4 — Airtable (free candidate database)")
    p("  Opening Airtable in your browser...")
    p("  1. Sign up or log in at airtable.com")
    p("  2. Click 'Add a base' → 'Start from scratch'")
    p("  3. Name it: AI Recruiter ATS")
    p("  4. Copy the base ID from the URL (looks like: appXXXXXXXXXXXXXX)")
    p("  5. Then go to: airtable.com/create/tokens to get your API token")
    webbrowser.open("https://airtable.com")
    time.sleep(2)
    webbrowser.open("https://airtable.com/create/tokens")

    api_key = ask("Paste your Airtable API token (starts with 'pat')")
    base_id = ask("Paste your Airtable Base ID (starts with 'app')")

    if not api_key.startswith("pat") and not api_key.startswith("key"):
        warn("Token doesn't look right — make sure you copied the full token")
    if not base_id.startswith("app"):
        warn("Base ID doesn't look right — copy it from the URL bar")

    # Test the connection
    resp = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    if resp.status_code == 200:
        ok("Airtable connection verified!")
        write_env("AIRTABLE_API_KEY", api_key)
        write_env("AIRTABLE_BASE_ID", base_id)

        # Auto-create all tables
        p("  Creating tables automatically...")
        old_key = os.environ.get("AIRTABLE_API_KEY", "")
        old_base = os.environ.get("AIRTABLE_BASE_ID", "")
        os.environ["AIRTABLE_API_KEY"]  = api_key
        os.environ["AIRTABLE_BASE_ID"]  = base_id
        result = subprocess.run(
            [sys.executable, "airtable_setup.py", "--base-id", base_id],
            capture_output=True, text=True
        )
        print("  " + result.stdout.replace("\n", "\n  ").strip())
        if result.returncode != 0:
            warn("Table setup had issues. You may need to create tables manually (see SETUP.md).")
        else:
            ok("All Airtable tables created!")
    else:
        err(f"Airtable connection failed: {resp.status_code} — check your token and base ID")
        if ask("Try again? (y/n)").lower() == "y":
            return setup_airtable()


# ── STEP 2: GMAIL APP PASSWORD ────────────────────────────────────────────────

def setup_gmail():
    head("STEP 2/4 — Gmail App Password (for sending emails)")
    p("  Opening Google Account security settings...")
    p("  1. Make sure 2-Step Verification is ON")
    p("  2. Go to: App Passwords (at the bottom of Security page)")
    p("  3. Select app: Mail  |  Select device: Mac")
    p("  4. Click Generate — copy the 16-character password")
    webbrowser.open("https://myaccount.google.com/apppasswords")

    app_password = ask("Paste your Gmail App Password (16 chars, spaces ok)")
    app_password = app_password.replace(" ", "")

    if len(app_password) != 16:
        warn(f"Expected 16 characters, got {len(app_password)}. Double-check you copied it all.")

    # Test SMTP
    p("  Testing Gmail connection...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("connorsavenas2@gmail.com", app_password)
        ok("Gmail SMTP verified!")
        write_env("GMAIL_APP_PASSWORD", app_password)
    except smtplib.SMTPAuthenticationError:
        err("Gmail authentication failed. Make sure 2FA is on and you're using an App Password (not your regular password).")
        if ask("Try again? (y/n)").lower() == "y":
            return setup_gmail()
    except Exception as e:
        err(f"Gmail test failed: {e}")


# ── STEP 3: CALENDLY ─────────────────────────────────────────────────────────

def setup_calendly():
    head("STEP 3/4 — Calendly (interview scheduling)")
    p("  Opening Calendly...")
    p("  1. Sign up or log in at calendly.com (free)")
    p("  2. Create a new Event Type: 'Final Interview — 30 min'")
    p("  3. Make sure Google Calendar is connected (Settings → Calendar Sync)")
    p("  4. Go to: Integrations → API & Webhooks → Generate API Key")
    p("  5. Also copy your booking page URL (e.g. calendly.com/connorsavenas/final-interview)")
    webbrowser.open("https://calendly.com/integrations/api_webhooks")

    api_key      = ask("Paste your Calendly API key (starts with 'eyJ')")
    booking_link = ask("Paste your Calendly booking link (the full URL)")

    # Get user URI
    p("  Fetching your Calendly user ID...")
    try:
        resp = requests.get(
            "https://api.calendly.com/users/me",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if resp.status_code == 200:
            user_uri = resp.json().get("resource", {}).get("uri", "")
            ok(f"Calendly verified! User: {user_uri.split('/')[-1][:20]}...")
            write_env("CALENDLY_API_KEY",      api_key)
            write_env("CALENDLY_USER_URI",     user_uri)
            write_env("CALENDLY_BOOKING_LINK", booking_link)
        else:
            err(f"Calendly API failed: {resp.status_code}. Check your API key.")
            if ask("Try again? (y/n)").lower() == "y":
                return setup_calendly()
    except Exception as e:
        err(f"Calendly test failed: {e}")


# ── STEP 4: NGROK STATIC DOMAIN ──────────────────────────────────────────────

def setup_ngrok():
    head("STEP 4/4 — ngrok (permanent webhook URL)")
    p("  ngrok is already installed.")
    p("  Opening ngrok dashboard...")
    p("  1. Sign up free at dashboard.ngrok.com")
    p("  2. Go to: Your Authtoken — copy it")
    p("  3. Then go to: Domains → New Domain → get your free static domain")
    p("     (looks like: something-something-xyz.ngrok-free.app)")
    webbrowser.open("https://dashboard.ngrok.com/get-started/your-authtoken")

    auth_token = ask("Paste your ngrok authtoken")
    try:
        result = subprocess.run(
            ["/usr/local/bin/ngrok", "config", "add-authtoken", auth_token],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("ngrok auth token saved!")
        else:
            err(f"ngrok auth failed: {result.stderr}")
    except Exception as e:
        err(f"ngrok config failed: {e}")

    webbrowser.open("https://dashboard.ngrok.com/domains")
    p("")
    p("  Now get your free static domain from the Domains page...")
    static_domain = ask("Paste your ngrok static domain (e.g. abc-xyz.ngrok-free.app)")
    static_domain = static_domain.replace("https://", "").replace("http://", "").strip("/")

    # Update webhook URL in .env
    webhook_url = f"https://{static_domain}"
    write_env("WEBHOOK_BASE_URL", webhook_url)
    ok(f"Webhook URL set to: {webhook_url}")

    # Update LaunchAgent plist to use static domain
    plist_path = Path.home() / "Library/LaunchAgents/com.connorsavenas.ai-recruiter-ngrok.plist"
    content = plist_path.read_text()
    updated = content.replace(
        "<string>http</string>\n        <string>5055</string>\n        <string>--log</string>",
        f"<string>http</string>\n        <string>5055</string>\n        <string>--domain={static_domain}</string>\n        <string>--log</string>"
    )
    plist_path.write_text(updated)
    ok("LaunchAgent updated with your static domain")


# ── FINAL: LOAD LAUNCH AGENTS & RUN SETUP ────────────────────────────────────

def activate_everything():
    head("ACTIVATING EVERYTHING")

    agents = [
        "com.connorsavenas.ai-recruiter-webhook",
        "com.connorsavenas.ai-recruiter-dashboard",
        "com.connorsavenas.ai-recruiter-ngrok",
    ]

    for agent in agents:
        plist = Path.home() / f"Library/LaunchAgents/{agent}.plist"
        # Unload first in case it's already loaded
        subprocess.run([LAUNCHCTL, "unload", str(plist)], capture_output=True)
        result = subprocess.run([LAUNCHCTL, "load", str(plist)], capture_output=True, text=True)
        if result.returncode == 0:
            ok(f"Started: {agent.split('.')[-1]}")
        else:
            warn(f"LaunchAgent load issue: {agent}\n    {result.stderr.strip()}")

    time.sleep(3)

    # Run python main.py setup
    p("\n  Running final setup (Calendly webhook registration)...")
    result = subprocess.run(
        [sys.executable, "main.py", "setup"],
        capture_output=True, text=True
    )
    print("  " + result.stdout.replace("\n", "\n  ").strip())

    # Register Calendly webhook with the real URL
    load_dotenv(ENV_PATH, override=True)
    calendly_key = os.getenv("CALENDLY_API_KEY", "")
    calendly_uri = os.getenv("CALENDLY_USER_URI", "")
    webhook_url  = os.getenv("WEBHOOK_BASE_URL", "")

    if calendly_key and calendly_uri and webhook_url:
        try:
            resp = requests.post(
                "https://api.calendly.com/webhook_subscriptions",
                headers={"Authorization": f"Bearer {calendly_key}", "Content-Type": "application/json"},
                json={"url": f"{webhook_url}/webhooks/calendly",
                      "events": ["invitee.created", "invitee.canceled"],
                      "user": calendly_uri, "scope": "user"}
            )
            if resp.status_code in (200, 201):
                ok("Calendly webhook registered — bookings will auto-trigger emails")
            else:
                warn(f"Calendly webhook: {resp.status_code} (may already exist)")
        except Exception as e:
            warn(f"Calendly webhook registration: {e}")


# ── ZAPIER INSTRUCTIONS ───────────────────────────────────────────────────────

def print_zapier_instructions():
    load_dotenv(ENV_PATH, override=True)
    webhook_url = os.getenv("WEBHOOK_BASE_URL", "YOUR-NGROK-URL")
    endpoint    = f"{webhook_url}/webhooks/application"

    head("FINAL STEP — Connect Job Boards via Zapier (free)")
    p(f"  Your webhook URL: {BOLD}{endpoint}{RESET}")
    p("")
    p("  Go to zapier.com and create these 3 free Zaps:\n")
    p(f"  {BOLD}ZAP 1 — Indeed{RESET}")
    p(  "  Trigger: Indeed → New Job Application")
    p(  "  Action:  Webhooks by Zapier → POST")
    p(f"  URL: {endpoint}")
    p(  '  Data: name={{applicant_name}}, email={{applicant_email}}, phone={{applicant_phone}},')
    p(  '        job_title={{job_title}}, source="Indeed"')
    p("")
    p(f"  {BOLD}ZAP 2 — LinkedIn Jobs{RESET}")
    p(  "  Trigger: LinkedIn → New Job Application (requires LinkedIn Recruiter)")
    p(  "  Action:  Webhooks by Zapier → POST")
    p(f"  URL: {endpoint}")
    p(  '  Data: name={{candidate_name}}, email={{email}}, source="LinkedIn"')
    p("")
    p(f"  {BOLD}ZAP 3 — Email Parser (catch-all){RESET}")
    p(  "  Trigger: Email by Zapier → New Inbound Email (forward resumes here)")
    p(  "  Action:  Webhooks by Zapier → POST")
    p(f"  URL: {endpoint}")
    p(  '  Data: name={{subject}}, email={{from_email}}, resume_text={{body_plain}}, source="Email"')
    p("")
    p(  f"  {BOLD}zapier.com is free for 100 tasks/month{RESET} — enough for ~3-5 applicants/day")
    p("")
    p(  "  Opening Zapier now...")
    webbrowser.open("https://zapier.com/app/zaps")


# ── SUMMARY ───────────────────────────────────────────────────────────────────

def print_summary():
    load_dotenv(ENV_PATH, override=True)
    webhook_url   = os.getenv("WEBHOOK_BASE_URL", "not set")
    airtable_set  = bool(os.getenv("AIRTABLE_API_KEY"))
    gmail_set     = bool(os.getenv("GMAIL_APP_PASSWORD"))
    calendly_set  = bool(os.getenv("CALENDLY_API_KEY"))

    head("SETUP COMPLETE — What's Now Running 24/7")
    ok("Webhook server (port 5055) — auto-restarts if it crashes")
    ok("Dashboard (port 5056) — open http://localhost:5056 anytime")
    ok("ngrok tunnel — permanent URL, never changes")
    ok("Email sequences — fires every morning at 9am automatically")
    ok("Weekly digest — emails you every Monday at 8am")
    p("")
    p(f"  {BOLD}Your webhook URL:{RESET} {webhook_url}")
    p(f"  {BOLD}Airtable:{RESET}       {'✓' if airtable_set  else '✗ not set'}")
    p(f"  {BOLD}Gmail:{RESET}          {'✓' if gmail_set     else '✗ not set'}")
    p(f"  {BOLD}Calendly:{RESET}       {'✓' if calendly_set  else '✗ not set'}")
    p("")
    p(f"  {BOLD}What happens now:{RESET}")
    p("  1. Someone applies on Indeed/LinkedIn → Zapier fires → webhook receives it")
    p("  2. Claude scores their resume automatically")
    p("  3. Score ≥ 7 → they get Calendly link by email")
    p("  4. Score ≤ 4 → they get a polite rejection")
    p("  5. They book → your Google Calendar updates + confirmation sent")
    p("  6. Morning of interview → run: python main.py prep --email THEIR_EMAIL --send")
    p("  7. You show up to one final Zoom, fully prepared")
    p("")
    p(f"  {BOLD}Dashboard:{RESET} http://localhost:5056")
    p(f"  {BOLD}Commands:{RESET}  python main.py --help")


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{BOLD}{'='*50}")
    print("  AI Recruiter — Final Setup Wizard")
    print(f"{'='*50}{RESET}")
    print("  Takes ~15 minutes. Opens browser tabs automatically.")
    print("  After this, everything runs by itself forever.\n")

    input(f"{BLUE}  Press Enter to start...{RESET}")

    load_dotenv(ENV_PATH, override=True)

    # Check what's already done
    airtable_done = bool(os.getenv("AIRTABLE_API_KEY")) and bool(os.getenv("AIRTABLE_BASE_ID"))
    gmail_done    = bool(os.getenv("GMAIL_APP_PASSWORD"))
    calendly_done = bool(os.getenv("CALENDLY_API_KEY"))
    ngrok_done    = "ngrok-free.app" in os.getenv("WEBHOOK_BASE_URL", "")

    if airtable_done:
        ok("Airtable already configured — skipping")
    else:
        setup_airtable()

    if gmail_done:
        ok("Gmail already configured — skipping")
    else:
        setup_gmail()

    if calendly_done:
        ok("Calendly already configured — skipping")
    else:
        setup_calendly()

    if ngrok_done:
        ok("ngrok static domain already configured — skipping")
    else:
        setup_ngrok()

    activate_everything()
    print_zapier_instructions()
    input(f"\n{BLUE}  Press Enter after setting up Zapier...{RESET}")
    print_summary()
