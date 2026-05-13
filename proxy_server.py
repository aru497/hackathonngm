"""
NGM Referral Pipeline — Foundry Proxy
=====================================
Sits between the browser (Hospital_Intake_Portal.html) and Azure AI
Foundry. Holds the API key so it never reaches the browser, and adapts
the OpenAI Responses API into the small JSON contract the HTML expects.

Run:
    pip install -r requirements.txt
    cp .env.example .env       # then edit with your real values
    python proxy_server.py

Endpoints:
    POST /api/agent1/start    body: { userId, intake }
    POST /api/agent1/reply    body: { responseId, userMessage }
    POST /api/agent2/match    body: { userId, riskLevel, language,
                                       personaNotes, preferredStyle?,
                                       volunteers }
    GET  /api/health
"""

from __future__ import annotations
import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

AGENT1_URL = os.environ.get("AGENT1_URL", "").strip()
AGENT2_URL = os.environ.get("AGENT2_URL", "").strip()
API_KEY = os.environ.get("FOUNDRY_API_KEY", "").strip()
API_VERSION = os.environ.get("FOUNDRY_API_VERSION", "2025-11-15-preview").strip()
TIMEOUT = float(os.environ.get("FOUNDRY_TIMEOUT", "120"))


def _with_api_version(url: str) -> str:
    """Append ?api-version=... to a Foundry URL if it isn't already there."""
    if not url:
        return url
    if "api-version=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}api-version={API_VERSION}"


AGENT1_URL = _with_api_version(AGENT1_URL)
AGENT2_URL = _with_api_version(AGENT2_URL)

if not (AGENT1_URL and API_KEY):
    print("WARNING: AGENT1_URL or FOUNDRY_API_KEY missing — set them in .env")

HEADERS = {
    "api-key": API_KEY,
    "Authorization": f"Bearer {API_KEY}",  # Foundry accepts either; both included for safety
    "Content-Type": "application/json",
}

app = Flask(__name__)
CORS(app)  # allow the browser (file:// or http://localhost:*) to call us


# ---------- helpers -------------------------------------------------------

def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    """Call a Foundry agent's Responses endpoint. Raises on HTTP error."""
    if not url:
        raise RuntimeError("Agent URL not configured in .env")
    r = requests.post(url, headers=HEADERS, json=body, timeout=TIMEOUT)
    if r.status_code >= 400:
        # Surface Foundry's own error JSON for easier debugging
        raise RuntimeError(f"Foundry {r.status_code}: {r.text[:1000]}")
    return r.json()


def _extract_text(resp: dict[str, Any]) -> str:
    """Pull the assistant's text reply out of a Responses API payload.
    Handles both the convenience `output_text` field and the canonical
    `output[].content[].text` shape."""
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    for item in resp.get("output", []) or []:
        if item.get("type") in ("message", "output_message"):
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text"):
                    val = c.get("text")
                    if isinstance(val, dict):  # some shapes nest as {"value": "..."}
                        val = val.get("value", "")
                    if val:
                        return val
    # Fallback: dump the whole thing so the user can see what came back
    return json.dumps(resp)[:2000]


_JSON_BLOCK_RE = re.compile(r"```json\s*(\{[\s\S]+?\})\s*```", re.MULTILINE)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Find the first ```json … ``` block in the agent's reply and parse it.
    Returns None if no block is found or parsing fails."""
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        # Some models forget the fence — try to find a bare {...} that looks
        # like one of our expected shapes (has userId or volunteerId).
        for cand in re.findall(r"\{[\s\S]+?\}", text):
            if '"userId"' in cand or '"volunteerId"' in cand:
                try:
                    return json.loads(cand)
                except json.JSONDecodeError:
                    continue
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# ---------- routes --------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "agent1_configured": bool(AGENT1_URL),
        "agent2_configured": bool(AGENT2_URL),
        "key_present": bool(API_KEY),
    })


@app.post("/api/agent1/start")
def agent1_start():
    """Open a new induction. Sends the intake context to Agent 1 and
    returns its first reply (a question to the user, in role)."""
    body = request.get_json(force=True) or {}
    user_id = body.get("userId")
    intake = body.get("intake") or {}
    if not user_id:
        return jsonify({"error": "userId required"}), 400

    msg = (
        f"Start induction for UserID={user_id}. Intake: "
        f"Risk={intake.get('riskLevel','?')}, "
        f"Language={intake.get('language','?')}, "
        f"Contact={intake.get('contactMethod','?')}, "
        f"Presenting={intake.get('presenting','')}, "
        f"Stressors={intake.get('stressors','')}."
    )

    try:
        resp = _post(AGENT1_URL, {"input": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    text = _extract_text(resp)
    parsed = _extract_json(text)
    return jsonify({
        "responseId": resp.get("id"),
        "reply": text,
        "done": parsed is not None,
        "json": parsed,
    })


@app.post("/api/agent1/reply")
def agent1_reply():
    """Continue an induction with the user's next message."""
    body = request.get_json(force=True) or {}
    response_id = body.get("responseId")
    user_message = body.get("userMessage")
    if not (response_id and user_message):
        return jsonify({"error": "responseId and userMessage required"}), 400

    try:
        resp = _post(AGENT1_URL, {
            "input": user_message,
            "previous_response_id": response_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    text = _extract_text(resp)
    parsed = _extract_json(text)
    return jsonify({
        "responseId": resp.get("id"),
        "reply": text,
        "done": parsed is not None,
        "json": parsed,
    })


@app.post("/api/agent2/match")
def agent2_match():
    """Ask Agent 2 (Matchmaker) to pick the best first-call volunteer.
    The host (HTML portal) sends the CURRENT volunteer pool snapshot,
    so Agent 2 always sees fresh loads."""
    body = request.get_json(force=True) or {}
    user_id = body.get("userId")
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    if not AGENT2_URL:
        return jsonify({
            "error": "AGENT2_URL not configured in .env — build Agent 2 in Foundry first."
        }), 500

    pool = body.get("volunteers") or []
    msg = (
        f"Match request for UserID={user_id}.\n"
        f"RiskLevel: {body.get('riskLevel','?')}\n"
        f"Language: {body.get('language','?')}\n"
        f"PersonaNotes: {body.get('personaNotes','')}\n"
        f"PreferredVolunteerStyle: {body.get('preferredStyle','')}\n\n"
        f"Volunteer pool (current snapshot):\n{json.dumps(pool, indent=2)}"
    )

    try:
        resp = _post(AGENT2_URL, {"input": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    text = _extract_text(resp)
    parsed = _extract_json(text)
    if not parsed:
        return jsonify({
            "error": "Agent 2 reply did not contain a parseable JSON block",
            "raw": text[:2000],
        }), 502
    return jsonify(parsed)


if __name__ == "__main__":
    print(f"NGM proxy listening on http://127.0.0.1:5000")
    print(f"  Agent 1 URL: {AGENT1_URL or '(NOT SET)'}")
    print(f"  Agent 2 URL: {AGENT2_URL or '(NOT SET — Agent 2 calls will 500)'}")
    print(f"  Key:         {'set' if API_KEY else '(NOT SET)'}")
    app.run(host="127.0.0.1", port=5000, debug=False)
