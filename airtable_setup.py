"""
Run this ONCE after creating your Airtable base to auto-create all tables and fields.
Usage: python airtable_setup.py --base-id appXXXXXXXXXXXXXX
"""

import requests
import sys
import argparse
from config import AIRTABLE_API_KEY

BASE_URL = "https://api.airtable.com/v0/meta/bases"
HEADERS  = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}


def create_base_schema(base_id: str):
    """Create all tables and fields for the AI Recruiter ATS."""

    tables_payload = {
        "tables": [
            {
                "name": "Candidates",
                "fields": [
                    {"name": "Name",              "type": "singleLineText"},
                    {"name": "Email",             "type": "email"},
                    {"name": "Phone",             "type": "phoneNumber"},
                    {"name": "Job_Title",         "type": "singleLineText"},
                    {"name": "Job_ID",            "type": "singleLineText"},
                    {"name": "Status",            "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "Applied"},{"name": "Called"},{"name": "Screened"},
                         {"name": "Qualified"},{"name": "Final_Round"},
                         {"name": "Hired"},{"name": "Rejected"}]}},
                    {"name": "Score",             "type": "number", "options": {"precision": 0}},
                    {"name": "Score_Summary",     "type": "multilineText"},
                    {"name": "Strengths",         "type": "multilineText"},
                    {"name": "Concerns",          "type": "multilineText"},
                    {"name": "Comp_Expectation",  "type": "singleLineText"},
                    {"name": "Availability",      "type": "singleLineText"},
                    {"name": "Call_ID",           "type": "singleLineText"},
                    {"name": "Call_Recording_URL","type": "url"},
                    {"name": "Transcript",        "type": "multilineText"},
                    {"name": "Applied_Date",      "type": "date", "options": {"dateFormat": {"name": "iso"}}},
                    {"name": "Called_Date",       "type": "date", "options": {"dateFormat": {"name": "iso"}}},
                    {"name": "Source",            "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "Indeed"},{"name": "LinkedIn"},{"name": "Handshake"},
                         {"name": "Referral"},{"name": "Outreach"},{"name": "Apollo"},
                         {"name": "Manual"},{"name": "Unknown"}]}},
                    {"name": "Notes",             "type": "multilineText"},
                    {"name": "Calendly_Booked",   "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
                    {"name": "Final_Interview_Date","type": "date", "options": {"dateFormat": {"name": "iso"}}},
                    {"name": "Recommend",         "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "Strong Yes"},{"name": "Yes"},
                         {"name": "Maybe"},{"name": "No"}]}}
                ]
            },
            {
                "name": "Jobs",
                "fields": [
                    {"name": "Job_Title",         "type": "singleLineText"},
                    {"name": "Job_ID",            "type": "singleLineText"},
                    {"name": "Type",              "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "1099"},{"name": "Internship"},{"name": "Part_Time"}]}},
                    {"name": "Description",       "type": "multilineText"},
                    {"name": "Requirements",      "type": "multilineText"},
                    {"name": "Pay_Range",         "type": "singleLineText"},
                    {"name": "Status",            "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "Active"},{"name": "Paused"},
                         {"name": "Filled"},{"name": "Closed"}]}},
                    {"name": "Posted_Date",       "type": "date", "options": {"dateFormat": {"name": "iso"}}},
                    {"name": "Applications_Count","type": "number", "options": {"precision": 0}},
                    {"name": "Qualified_Count",   "type": "number", "options": {"precision": 0}}
                ]
            },
            {
                "name": "Call_Logs",
                "fields": [
                    {"name": "Call_ID",           "type": "singleLineText"},
                    {"name": "Candidate_Name",    "type": "singleLineText"},
                    {"name": "Candidate_Email",   "type": "email"},
                    {"name": "Job_Title",         "type": "singleLineText"},
                    {"name": "Direction",         "type": "singleSelect",
                     "options": {"choices": [{"name": "Outbound"},{"name": "Inbound"}]}},
                    {"name": "Status",            "type": "singleSelect",
                     "options": {"choices": [
                         {"name": "Completed"},{"name": "No_Answer"},
                         {"name": "Voicemail"},{"name": "Failed"}]}},
                    {"name": "Duration_Seconds",  "type": "number", "options": {"precision": 0}},
                    {"name": "Score",             "type": "number", "options": {"precision": 0}},
                    {"name": "Recording_URL",     "type": "url"},
                    {"name": "Transcript",        "type": "multilineText"},
                    {"name": "Called_At",         "type": "date", "options": {"dateFormat": {"name": "iso"}}}
                ]
            }
        ]
    }

    url  = f"{BASE_URL}/{base_id}/tables"
    resp = requests.post(url, headers=HEADERS, json=tables_payload)

    if resp.status_code == 200:
        tables = resp.json().get("tables", [])
        print(f"✓ Created {len(tables)} tables:")
        for t in tables:
            print(f"  • {t['name']} — {len(t.get('fields', []))} fields")
    else:
        print(f"Error: {resp.status_code} — {resp.text}")
        print("\nNote: If tables already exist, this is expected. Your base is ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-id", required=True, help="Your Airtable base ID (appXXXXXXXXXXXXXX)")
    args = parser.parse_args()
    print(f"Setting up Airtable base: {args.base_id}")
    create_base_schema(args.base_id)
    print("\nDone! Add AIRTABLE_BASE_ID to your .env file.")
