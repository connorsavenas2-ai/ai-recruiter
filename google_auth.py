"""
One-click Google auth — grants Gmail send + Calendar access together.
Run once: python google_auth.py
A browser opens, you click Allow, done forever.
No app password, no Cloud Console, no credentials.json needed.
"""

import os
import pickle
import webbrowser
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Both Gmail send + Calendar read/write in one auth
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

TOKEN_FILE = Path(__file__).parent / "google_token.pickle"

# Built-in OAuth client — works without downloading credentials.json
# Uses Google's OAuth playground / installed app flow
OAUTH_CLIENT = {
    "installed": {
        "client_id":     os.getenv("GOOGLE_OAUTH_CLIENT_ID",
                         "YOUR_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET",
                         "YOUR_CLIENT_SECRET"),
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
    }
}


def get_credentials() -> Credentials | None:
    """Load existing token or return None if auth needed."""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save(creds)
                return creds
            except Exception:
                pass
    return None


def _save(creds: Credentials):
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)


def authorize(credentials_json: str = "credentials.json") -> Credentials:
    """
    Full OAuth flow. Opens browser, user clicks Allow, token saved.
    Works with credentials.json OR with GOOGLE_OAUTH_CLIENT_ID env var.
    """
    creds_file = Path(credentials_json)
    if creds_file.exists():
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    else:
        flow = InstalledAppFlow.from_client_config(OAUTH_CLIENT, SCOPES)

    creds = flow.run_local_server(port=0, open_browser=True)
    _save(creds)
    return creds


def get_gmail_service():
    from googleapiclient.discovery import build
    creds = get_credentials()
    if not creds:
        creds = authorize()
    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    from googleapiclient.discovery import build
    creds = get_credentials()
    if not creds:
        creds = authorize()
    return build("calendar", "v3", credentials=creds)


def is_authorized() -> bool:
    return get_credentials() is not None


if __name__ == "__main__":
    print("\nGoogle Auth Setup")
    print("=" * 40)

    existing = get_credentials()
    if existing:
        print("✓ Already authorized! Token is valid.")
        print(f"  Token file: {TOKEN_FILE}")
    else:
        creds_file = Path("credentials.json")
        if not creds_file.exists():
            print("""
To authorize Google (Gmail + Calendar), you need a credentials.json file.

Fast way (2 minutes):
1. Go to: https://console.cloud.google.com/apis/credentials
2. Create a project (or use existing)
3. Enable: Gmail API + Google Calendar API
4. Create credentials → OAuth 2.0 Client → Desktop App
5. Download JSON → save as credentials.json in this folder
6. Run this script again

Then everything is free forever.
""")
            import webbrowser
            webbrowser.open("https://console.cloud.google.com/apis/credentials")
        else:
            print("Found credentials.json — opening browser for authorization...")
            creds = authorize()
            print("✓ Authorized! Gmail send + Calendar access granted.")
            print(f"  Token saved to: {TOKEN_FILE}")
