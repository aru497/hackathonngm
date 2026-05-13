#!/usr/bin/env python3
"""
Probe several URL variants and auth modes to find the one that works for
your Foundry agent. Run:

    python3 probe_endpoint.py

Reads AGENT1_URL + FOUNDRY_API_KEY from .env. Tries every reasonable
combination and reports which one returned HTTP 200.
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
base = os.environ.get("AGENT1_URL", "").strip().split("?")[0]  # strip any existing query
key = os.environ.get("FOUNDRY_API_KEY", "").strip()

if not (base and key):
    print("✗ AGENT1_URL or FOUNDRY_API_KEY missing in .env")
    sys.exit(1)

# Build URL variants
def url_variants(u):
    out = [u]
    # without /v1/
    if "/openai/v1/responses" in u:
        out.append(u.replace("/openai/v1/responses", "/openai/responses"))
    # if it's an agent-endpoint URL, also try the "applications" rewrite
    if "/agents/" in u and "/endpoint/protocols/" in u:
        # /agents/<X>/endpoint/protocols/... -> /applications/<X>/protocols/...
        out.append(u.replace("/agents/", "/applications/").replace("/endpoint/protocols/", "/protocols/"))
        # same but without /v1/
        out.append(out[-1].replace("/openai/v1/responses", "/openai/responses"))
    return list(dict.fromkeys(out))  # dedupe, preserve order

API_VERSIONS = ["2025-11-15-preview", "2025-04-01-preview", "preview", "v1"]
AUTH_MODES = [
    ("api-key header",        {"api-key": key}),
    ("Bearer Authorization",  {"Authorization": f"Bearer {key}"}),
]
BODY = {"input": "Say hi in 3 words."}

print(f"Base URL: {base}\n")

best = None
for u in url_variants(base):
    for ver in API_VERSIONS:
        for label, auth in AUTH_MODES:
            full = f"{u}?api-version={ver}"
            headers = {"Content-Type": "application/json", **auth}
            try:
                r = requests.post(full, headers=headers, json=BODY, timeout=30)
                code = r.status_code
            except Exception as e:
                print(f"  [skip] {full} ({label}): {e}")
                continue
            tag = "✓" if code == 200 else "✗"
            print(f"  {tag} {code}  {label:<22}  api-version={ver:<22}  {u}")
            if code == 200 and best is None:
                best = (u, ver, label, headers, r)

print()
if best:
    u, ver, label, headers, r = best
    print("================ WORKING COMBINATION ================")
    print(f"  URL:         {u}")
    print(f"  api-version: {ver}")
    print(f"  Auth:        {label}")
    print()
    print("Update your .env to:")
    print(f"  AGENT1_URL={u}")
    print(f"  FOUNDRY_API_VERSION={ver}")
    print()
    print("Agent replied:")
    data = r.json()
    text = data.get("output_text") or ""
    if not text:
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text"):
                    t = c.get("text")
                    text = t.get("value") if isinstance(t, dict) else t
    print(f"  {text or json.dumps(data)[:500]}")
else:
    print("================ NOTHING WORKED ================")
    print("Most likely: the agent needs to be PUBLISHED in Foundry before")
    print("its endpoint is callable. Open the agent in Foundry, look for")
    print("a 'Publish Agent' button (top-right or in a 3-dot menu), and")
    print("publish. After publishing, Foundry shows a new URL containing")
    print("'/applications/<app-name>/' instead of '/agents/<name>/endpoint/'.")
    print("Paste that new URL into .env and re-run this probe.")
