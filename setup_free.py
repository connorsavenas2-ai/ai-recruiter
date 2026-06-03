#!/usr/bin/env python3
"""
One-command free setup.
Run: python setup_free.py

Does everything in ~5 minutes:
1. Google OAuth (Gmail send + Calendar) — browser opens, you click Allow
2. Starts Cloudflare tunnel — gets your free public URL
3. Writes the URL to .env automatically
4. Starts all background services
5. Opens your ATS dashboard

Cost: $0. Forever.
"""

import os
import sys
import json
import time
import subprocess
import threading
import webbrowser
from pathlib import Path
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent / ".env"
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

G  = "\033[92m"
Y  = "\033[93m"
R  = "\033[91m"
B  = "\033[94m"
C  = "\033[96m"
W  = "\033[1m"
X  = "\033[0m"

def ok(m):   print(f"{G}  ✓ {m}{X}")
def warn(m): print(f"{Y}  ⚠ {m}{X}")
def err(m):  print(f"{R}  ✗ {m}{X}")
def head(m): print(f"\n{W}{C}{'─'*50}\n  {m}\n{'─'*50}{X}")
def inp(m):  return input(f"{B}  → {m}: {X}").strip()


# ── STEP 1: GOOGLE OAUTH ──────────────────────────────────────────────────────

def setup_google():
    head("STEP 1 — Google Auth (Gmail + Calendar)")
    print("  This gives Jenny permission to send emails and")
    print("  read your calendar — all from your existing Gmail.\n")

    from google_auth import is_authorized, authorize, TOKEN_FILE

    if is_authorized():
        ok("Already authorized — skipping")
        return

    creds_file = Path("credentials.json")
    if not creds_file.exists():
        print(f"""
  To authorize Google, you need a credentials.json file.
  It takes 2 minutes:

  {W}1.{X} Go to: {B}https://console.cloud.google.com/apis/credentials{X}
  {W}2.{X} Create project → Enable Gmail API + Google Calendar API
  {W}3.{X} Credentials → Create → OAuth 2.0 Client → Desktop App → Download JSON
  {W}4.{X} Save the file as {W}credentials.json{X} in this folder:
     {Path(__file__).parent}
  {W}5.{X} Come back here and press Enter
""")
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
        input(f"{B}  Press Enter once credentials.json is saved...{X}")
        if not creds_file.exists():
            err("credentials.json still not found. Skipping Google auth.")
            warn("Email and Calendar features won't work until you complete this.")
            return

    print("  Opening browser — click Allow when Google asks for permission...")
    try:
        authorize()
        ok("Google authorized! Gmail send + Calendar access granted.")
        ok(f"Token saved to: {TOKEN_FILE}")
    except Exception as e:
        err(f"Authorization failed: {e}")


# ── STEP 2: CLOUDFLARE TUNNEL ─────────────────────────────────────────────────

_tunnel_url = None

def start_cloudflare_tunnel():
    global _tunnel_url
    head("STEP 2 — Free Public URL (Cloudflare Tunnel)")
    print("  Getting your permanent public URL — no account needed...")

    cloudflared = "/usr/local/bin/cloudflared"
    if not Path(cloudflared).exists():
        warn("cloudflared not found. Installing...")
        subprocess.run(["brew", "install", "cloudflare/cloudflare/cloudflared"],
                      capture_output=True)

    # Start tunnel in background, capture URL from logs
    log_file = LOGS_DIR / "tunnel.log"
    proc = subprocess.Popen(
        [cloudflared, "tunnel", "--url", "http://localhost:5055",
         "--logfile", str(log_file)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

    print("  Waiting for URL...")
    url = None
    for _ in range(30):
        time.sleep(1)
        try:
            output = subprocess.check_output(
                ["grep", "-o", "https://[a-z0-9-]*\\.trycloudflare\\.com", str(log_file)],
                stderr=subprocess.DEVNULL, text=True
            ).strip().split("\n")[0]
            if output.startswith("https://"):
                url = output
                break
        except:
            pass
        # Also check stdout
        try:
            line = proc.stdout.readline().decode("utf-8", errors="ignore")
            if "trycloudflare.com" in line:
                import re
                m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if m:
                    url = m.group(0)
                    break
        except:
            pass

    if url:
        _tunnel_url = url
        ok(f"Your public URL: {W}{url}{X}")
        set_key(str(ENV_PATH), "WEBHOOK_BASE_URL", url)
        ok(f"Saved to .env as WEBHOOK_BASE_URL")
    else:
        warn("Couldn't capture tunnel URL automatically.")
        warn(f"Check {log_file} for the URL and paste it into .env as WEBHOOK_BASE_URL")

    return proc


# ── STEP 3: START ALL SERVICES ────────────────────────────────────────────────

def start_services():
    head("STEP 3 — Starting All Services")
    agents = [
        ("Webhook server",  "com.connorsavenas.ai-recruiter-webhook"),
        ("ATS Dashboard",   "com.connorsavenas.ai-recruiter-ats"),
        ("Cloudflare tunnel","com.connorsavenas.ai-recruiter-tunnel"),
    ]
    for name, label in agents:
        plist = Path.home() / f"Library/LaunchAgents/{label}.plist"
        subprocess.run(["/bin/launchctl", "unload", str(plist)],
                       capture_output=True)
        result = subprocess.run(["/bin/launchctl", "load", str(plist)],
                                capture_output=True, text=True)
        if result.returncode == 0:
            ok(f"{name} started")
        else:
            warn(f"{name}: {result.stderr.strip() or 'check plist'}")

    time.sleep(2)

    # Verify services are running
    running = subprocess.check_output(
        ["launchctl", "list"], text=True
    )
    for name, label in agents:
        if label in running:
            ok(f"{name}: running")
        else:
            warn(f"{name}: not found in launchctl")


# ── STEP 4: SET GIRLFRIEND CREDENTIALS ───────────────────────────────────────

def setup_users():
    head("STEP 4 — Set Your Login Passwords")
    load_dotenv(ENV_PATH, override=True)

    from werkzeug.security import generate_password_hash

    print(f"  Your username is: {W}connor{X}")
    pwd1 = inp("Set your password (type what you want)")
    if pwd1:
        set_key(str(ENV_PATH), "ADMIN_PASSWORD", pwd1)
        ok("Your password saved")

    print()
    gf_name = inp("Your girlfriend's first name (for her login)")
    if gf_name:
        gf_user = gf_name.lower().replace(" ", "")
        gf_pwd  = inp(f"Set {gf_name}'s password")
        set_key(str(ENV_PATH), "USER2_USERNAME",     gf_user)
        set_key(str(ENV_PATH), "USER2_PASSWORD",     gf_pwd)
        set_key(str(ENV_PATH), "USER2_DISPLAY_NAME", gf_name)
        set_key(str(ENV_PATH), "USER2_AVATAR",       gf_name[0].upper())
        ok(f"{gf_name}'s account created (username: {gf_user})")

    company = inp("Business name (press Enter to keep current)")
    if company:
        set_key(str(ENV_PATH), "COMPANY_NAME", company)
        ok(f"Company name set: {company}")


# ── SUMMARY ───────────────────────────────────────────────────────────────────

def print_summary():
    load_dotenv(ENV_PATH, override=True)
    tunnel_url = os.getenv("WEBHOOK_BASE_URL", "not set yet")
    company    = os.getenv("COMPANY_NAME", "your company")

    head("ALL DONE — Your System Is Live")
    print(f"""
  {W}ATS Dashboard:{X}      http://localhost:5057
  {W}Public URL:{X}         {tunnel_url}
  {W}Apply form:{X}         {tunnel_url}/apply/JOB-XXXX
  {W}Candidate portal:{X}   {tunnel_url}/portal
  {W}Book interview:{X}     {tunnel_url}/book/RECORD_ID

  {W}Your login:{X}         Username: connor
  {W}Girlfriend login:{X}   Username: {os.getenv('USER2_USERNAME', 'not set yet')}

  {W}What runs automatically:{X}
    ✓ Applications scored by AI (Groq - free)
    ✓ Qualified candidates emailed Calendly/booking link
    ✓ Booking page shows your real calendar availability
    ✓ Confirmation emails sent on booking
    ✓ 24-hour + 1-hour reminders sent automatically
    ✓ No-show follow-ups sent automatically
    ✓ Candidates can check status at /portal

  {W}Cost:{X} {G}$0/month{X}

  {W}To view your dashboard:{X}
    Open: http://localhost:5057
    Or share: {tunnel_url}/ats/ with your girlfriend

  {W}To add your first job:{X}
    python main.py add-job
    Then share: {tunnel_url}/apply/JOB-XXXX
""")
    webbrowser.open("http://localhost:5057")


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
{W}{'='*50}
  Free Setup — {Path('.env').parent.name}
{'='*50}{X}
  Everything costs $0. Takes ~5 minutes.
""")
    load_dotenv(ENV_PATH)
    input(f"{B}  Press Enter to start...{X}")

    setup_google()
    start_cloudflare_tunnel()
    setup_users()
    start_services()
    print_summary()
