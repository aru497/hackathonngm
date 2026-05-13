#!/usr/bin/env python3
"""
One-shot verification: pings both Agent 1 and Agent 2 endpoints with a
representative payload and prints a clean pass/fail report.

Run BEFORE launching the proxy:
    python3 verify_agents.py

Reads AGENT1_URL, AGENT2_URL, FOUNDRY_API_KEY, FOUNDRY_API_VERSION from .env.
"""
from __future__ import annotations
import json
import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("FOUNDRY_API_KEY", "").strip()
API_VERSION = os.environ.get("FOUNDRY_API_VERSION", "2025-11-15-preview").strip()
AGENT1_URL = os.environ.get("AGENT1_URL", "").strip()
AGENT2_URL = os.environ.get("AGENT2_URL", "").strip()

if not API_KEY:
    print("✗ FOUNDRY_API_KEY missing from .env")
    sys.exit(1)


def _with_version(u):
    if "api-version=" in u: return u
    return f"{u}{'&' if '?' in u else '?'}api-version={API_VERSION}"


HEADERS = {
    "api-key": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def _extract_text(resp):
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    for item in resp.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                t = c.get("text")
                return t.get("value") if isinstance(t, dict) else (t or "")
    return ""


def _extract_json(text):
    m = re.search(r"```json\s*(\{[\s\S]+?\})\s*```", text)
    if not m: return None
    try: return json.loads(m.group(1))
    except json.JSONDecodeError: return None


def ping(name, url, body):
    if not url:
        return (False, f"{name}: URL not configured in .env")
    full = _with_version(url)
    print(f"→ {name}")
    print(f"  URL: {full}")
    try:
        r = requests.post(full, headers=HEADERS, json=body, timeout=60)
    except Exception as e:
        return (False, f"{name}: network error — {e}")
    if r.status_code >= 400:
        return (False, f"{name}: HTTP {r.status_code} — {r.text[:600]}")
    data = r.json()
    text = _extract_text(data)
    return (True, text)


# Agent 1: induction kickoff
ok1, msg1 = ping("Agent 1 (Induction)", AGENT1_URL, {
    "input": "Start induction for UserID=PING_TEST. Intake: Risk=Medium, Language=English, Contact=Phone (Evening), Presenting=connectivity check, Stressors=none."
})
print(f"  {'✓' if ok1 else '✗'}  {(msg1 or '')[:300]}\n")

# Agent 2: tiny match request with a 2-volunteer pool
sample_pool = [
    {"id":"VOL_TEST_A","name":"Test A","accred":3,"specialties":"general","language":"English","currentLoad":1,"status":"Available","persona":"calm"},
    {"id":"VOL_TEST_B","name":"Test B","accred":3,"specialties":"general","language":"English","currentLoad":3,"status":"Available","persona":"direct"},
]
match_msg = (
    "Match request for UserID=PING_TEST.\n"
    "RiskLevel: High\nLanguage: English\nPersonaNotes: connectivity check.\nPreferredVolunteerStyle: calm/reflective\n\n"
    f"Volunteer pool (current snapshot):\n{json.dumps(sample_pool, indent=2)}"
)
ok2, msg2 = ping("Agent 2 (Matchmaker)", AGENT2_URL, {"input": match_msg})
print(f"  {'✓' if ok2 else '✗'}  {(msg2 or '')[:600]}\n")

# Parse the matchmaker reply
if ok2:
    parsed = _extract_json(msg2)
    if parsed and parsed.get("volunteerId"):
        print(f"  ✓ Agent 2 returned valid JSON. Picked: {parsed['volunteerId']}  reason: {parsed.get('reason','—')[:200]}\n")
    elif parsed:
        print(f"  ⚠ Agent 2 returned JSON but no volunteerId. Body: {json.dumps(parsed)[:300]}\n")
    else:
        print(f"  ⚠ Agent 2 reply didn't contain a parseable ```json block. The matchmaker prompt may need tightening.\n")

# Overall summary
print("=" * 60)
print(f"  Agent 1 (Induction):  {'CONNECTED ✓' if ok1 else 'FAILED ✗'}")
print(f"  Agent 2 (Matchmaker): {'CONNECTED ✓' if ok2 else 'FAILED ✗'}")
print("=" * 60)
if ok1 and ok2:
    print("\n✓ Both agents are wired up. Run `python3 proxy_server.py` next.")
    sys.exit(0)
else:
    print("\n✗ Fix the failures above before launching the proxy.")
    sys.exit(1)
