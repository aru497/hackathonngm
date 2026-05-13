#!/usr/bin/env python3
"""
Standalone connectivity test for Agent 1.
Run this BEFORE launching the proxy to verify your endpoint and key
work end-to-end.

    pip install python-dotenv requests
    python test_agent1.py

Reads AGENT1_URL and FOUNDRY_API_KEY from .env.
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("AGENT1_URL", "").strip()
key = os.environ.get("FOUNDRY_API_KEY", "").strip()
api_version = os.environ.get("FOUNDRY_API_VERSION", "2025-11-15-preview").strip()

if not (url and key):
    print("✗ AGENT1_URL or FOUNDRY_API_KEY missing from .env")
    sys.exit(1)

# Append api-version query parameter (required by Foundry agent endpoints)
sep = "&" if "?" in url else "?"
full_url = f"{url}{sep}api-version={api_version}"

print(f"→ POST {full_url}")
print(f"  with key {key[:8]}…{key[-4:]}")
try:
    r = requests.post(
        full_url,
        headers={
            "api-key": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={"input": "Say a single short greeting so I know you're online. No more than 8 words."},
        timeout=60,
    )
except Exception as e:
    print(f"✗ Network error: {e}")
    sys.exit(1)

print(f"  HTTP {r.status_code}\n")

if r.status_code >= 400:
    print("✗ Foundry rejected the request. Body:")
    print(r.text[:2000])
    print("\nCommon causes:")
    print("  • Key copied with a trailing space or newline")
    print("  • URL pointed at the wrong agent (Agent1 vs your actual name)")
    print("  • Agent not yet saved/published in Foundry")
    print("  • Wrong protocol — make sure URL ends in /v1/responses")
    sys.exit(1)

data = r.json()

# Try to extract just the text reply for a clean visual check
text = data.get("output_text", "")
if not text:
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                t = c.get("text")
                if isinstance(t, dict):
                    t = t.get("value", "")
                if t:
                    text = t
                    break
        if text:
            break

print("✓ Agent replied:")
print(f"  {text or '(no text in response — dumping raw payload below)'}")
print()
print("Raw response (first 1500 chars):")
print(json.dumps(data, indent=2)[:1500])
print()
print("✓ All good. Now run: python proxy_server.py")
