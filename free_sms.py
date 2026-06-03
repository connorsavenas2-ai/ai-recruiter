"""
Free SMS via email-to-carrier gateways.
Sends texts through Gmail — completely free, no Twilio needed.
Works for all major US carriers.

How it works:
  phonenumber@txt.att.net     → AT&T text message
  phonenumber@vtext.com       → Verizon text message
  phonenumber@tmomail.net     → T-Mobile text message
  phonenumber@messaging.sprintpcs.com → Sprint/T-Mobile

We ask for carrier on the booking form. If unknown, we try the top 3.
"""

import re
import os

# Major US carrier gateways (covers ~95% of US phones)
CARRIER_GATEWAYS = {
    "att":       "{number}@txt.att.net",
    "verizon":   "{number}@vtext.com",
    "tmobile":   "{number}@tmomail.net",
    "sprint":    "{number}@messaging.sprintpcs.com",
    "boost":     "{number}@sms.myboostmobile.com",
    "cricket":   "{number}@mms.cricketwireless.net",
    "metro":     "{number}@mymetropcs.com",
    "uscellular":"{number}@email.uscc.net",
    "googlefi":  "{number}@msg.fi.google.com",
}

# When carrier unknown, try these 3 (covers ~80% of US)
DEFAULT_GATEWAYS = ["att", "verizon", "tmobile"]


def _clean_phone(phone: str) -> str:
    """Strip to digits only, remove country code."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return digits


def send_free_sms(phone: str, message: str, carrier: str = "") -> bool:
    """
    Send SMS via email-to-carrier gateway using Gmail.
    carrier: 'att', 'verizon', 'tmobile', etc. (optional — tries all if unknown)
    Returns True if at least one gateway succeeded.
    """
    from email_outreach import _send_gmail_api as _send

    number = _clean_phone(phone)
    if len(number) != 10:
        print(f"[SMS] Invalid phone number: {phone}")
        return False

    # Truncate message to 160 chars (SMS limit)
    sms_body = message[:160]

    if carrier and carrier.lower() in CARRIER_GATEWAYS:
        # Known carrier — send to just that gateway
        gateway = CARRIER_GATEWAYS[carrier.lower()].format(number=number)
        try:
            _send(gateway, "", sms_body)
            print(f"[SMS] Sent to {number} via {carrier}")
            return True
        except Exception as e:
            print(f"[SMS] Failed via {carrier}: {e}")
            return False
    else:
        # Unknown carrier — try top 3, first success wins
        for c in DEFAULT_GATEWAYS:
            gateway = CARRIER_GATEWAYS[c].format(number=number)
            try:
                _send(gateway, "", sms_body)
                print(f"[SMS] Sent to {number} via {c} gateway")
                return True
            except Exception as e:
                print(f"[SMS] {c} gateway failed: {e}")
                continue
        return False


def send_sms(phone: str, message: str, carrier: str = "") -> bool:
    """Public interface — same as Twilio's send_sms but free."""
    return send_free_sms(phone, message, carrier)


# Carrier detection by area code (rough — covers common US carriers)
AREA_CODE_HINTS = {
    # These are rough heuristics only
    "att":     ["205","256","334","251","907","480","520","602","623","928"],
    "verizon": ["201","908","732","848","609","856","551"],
    "tmobile": ["206","425","253","360","509"],
}

def guess_carrier(phone: str) -> str:
    """Very rough carrier guess from area code. Returns '' if uncertain."""
    number = _clean_phone(phone)
    if len(number) < 10:
        return ""
    area = number[:3]
    for carrier, codes in AREA_CODE_HINTS.items():
        if area in codes:
            return carrier
    return ""  # unknown — try all gateways
