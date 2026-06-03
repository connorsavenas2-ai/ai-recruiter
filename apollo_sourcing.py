"""
Apollo.io candidate sourcing — searches for candidates matching job requirements.
"""

import requests
from config import APOLLO_API_KEY

BASE_URL = "https://api.apollo.io/v1"
HEADERS  = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": APOLLO_API_KEY
}


def search_candidates(
    job_titles: list,
    location: str = "United States",
    keywords: list = None,
    page: int = 1,
    per_page: int = 25
) -> list:
    """
    Search Apollo.io for candidates matching job titles and keywords.
    Returns list of people with name, email, phone, LinkedIn URL.
    """
    payload = {
        "person_titles": job_titles,
        "person_locations": [location],
        "q_keywords": " ".join(keywords) if keywords else "",
        "page": page,
        "per_page": per_page,
        "prospected_by_current_team": "no"
    }

    resp = requests.post(f"{BASE_URL}/mixed_people/search", headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()

    candidates = []
    for person in data.get("people", []):
        email = person.get("email", "")
        phone = (person.get("phone_numbers") or [{}])[0].get("sanitized_number", "")
        candidates.append({
            "name":     f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "email":    email,
            "phone":    phone,
            "linkedin": person.get("linkedin_url", ""),
            "title":    person.get("title", ""),
            "company":  person.get("organization_name", ""),
            "location": person.get("city", "") + ", " + person.get("state", "")
        })
    return [c for c in candidates if c["email"]]  # only return people with emails


def enrich_candidate(email: str) -> dict:
    """Get detailed info about a candidate by email."""
    payload = {"email": email, "reveal_personal_emails": True}
    resp = requests.post(f"{BASE_URL}/people/match", headers=HEADERS, json=payload)
    resp.raise_for_status()
    person = resp.json().get("person", {})
    return {
        "name":     f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
        "email":    person.get("email", email),
        "phone":    (person.get("phone_numbers") or [{}])[0].get("sanitized_number", ""),
        "linkedin": person.get("linkedin_url", ""),
        "title":    person.get("title", ""),
        "company":  person.get("organization_name", ""),
        "headline": person.get("headline", ""),
        "summary":  f"{person.get('title', '')} at {person.get('organization_name', '')}"
    }


ROLE_SEARCH_CONFIGS = {
    "finance_analyst": {
        "titles": ["Financial Analyst", "Finance Analyst", "Junior Financial Analyst", "Finance Associate"],
        "keywords": ["financial modeling", "Excel", "finance", "FP&A"]
    },
    "marketing": {
        "titles": ["Marketing Coordinator", "Marketing Associate", "Digital Marketing Specialist", "Growth Marketer"],
        "keywords": ["marketing", "social media", "content", "SEO"]
    },
    "sales": {
        "titles": ["Sales Representative", "Account Executive", "Business Development", "SDR"],
        "keywords": ["sales", "CRM", "pipeline", "outreach"]
    },
    "operations": {
        "titles": ["Operations Analyst", "Operations Coordinator", "Business Analyst", "Process Analyst"],
        "keywords": ["operations", "process improvement", "data analysis"]
    },
    "software_engineer": {
        "titles": ["Software Engineer", "Full Stack Developer", "Backend Engineer", "Frontend Developer"],
        "keywords": ["Python", "JavaScript", "React", "API"]
    },
    "data_analyst": {
        "titles": ["Data Analyst", "Business Intelligence Analyst", "Analytics Analyst"],
        "keywords": ["SQL", "Python", "Tableau", "data analysis"]
    }
}


def source_for_job(job_type_key: str, location: str = "United States", limit: int = 50) -> list:
    """Use a preset config to source candidates for common role types."""
    config = ROLE_SEARCH_CONFIGS.get(job_type_key, {})
    if not config:
        raise ValueError(f"Unknown job type: {job_type_key}. Options: {list(ROLE_SEARCH_CONFIGS.keys())}")

    all_candidates = []
    page = 1
    while len(all_candidates) < limit:
        batch = search_candidates(
            job_titles=config["titles"],
            location=location,
            keywords=config["keywords"],
            page=page,
            per_page=min(25, limit - len(all_candidates))
        )
        if not batch:
            break
        all_candidates.extend(batch)
        page += 1

    return all_candidates[:limit]
