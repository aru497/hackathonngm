# Agent 2 (Matchmaker) — Build Walkthrough

Click-by-click steps. Same flow as Agent 1, with a few differences
called out below. Keep this open in a second tab while you build.

The full Foundry config and the system prompt itself live in
`Agent2_Foundry_Setup.md`. This walkthrough just sequences the clicks.

---

## 1. Create the new agent
Left sidebar → **Agents** → **+ New agent**.

Set:
- **Name:** `Agent2`  (or `matchmaker` — whichever you prefer)
- **Description:** Picks the best first-call volunteer for an inducted user. Lowest-load rule.
- **Model:** `gpt-4o-mini`
- **Temperature:** `0.2`  (lower than Agent 1 — we want deterministic, repeatable matches)
- **Max response tokens:** `400`

## 2. Paste the system instructions
Open `Agent2_Foundry_Setup.md` (in your workspace). Copy everything
between the two `=====` lines under **3. System Instructions**.
Paste into Foundry's **Instructions** field.

## 3. Leave ALL tools off
- Code Interpreter: **OFF**
- Knowledge / File Search: **OFF**
- Web Search: **OFF**
- Function calling: **OFF**

This is different from Agent 1. Agent 2 has no files attached and no
tools enabled. The proxy server sends the current volunteer pool in
every message body, so the agent always sees fresh loads. Files would
just make it stale.

## 4. Memory, Knowledge, Guardrail
All **OFF**. The matcher is stateless on purpose.

## 5. Save
Top-right **Save** button.

## 6. Open Playground

### Test 1 — Standard match (verifies the LEAST-LOAD rule)
Paste:
```
Match request for UserID=HOSP_99.
RiskLevel: High
Language: English
PersonaNotes: Worn down by financial pressure and isolation; wants non-judgemental peer support.
PreferredVolunteerStyle: Steady, non-judgemental, encouraging

Volunteer pool (current snapshot):
[
  { "id": "VOL_001", "name": "Sarah J.", "accred": 3, "specialties": "Youth, Lived Experience", "language": "English", "currentLoad": 2, "status": "Available", "persona": "Warm, energetic, patient" },
  { "id": "VOL_002", "name": "Mark T.", "accred": 2, "specialties": "Financial Stress, Men's Health", "language": "English", "currentLoad": 4, "status": "Busy", "persona": "Direct, proactive, calm" },
  { "id": "VOL_003", "name": "Priya N.", "accred": 3, "specialties": "Anxiety, Cultural Identity", "language": "English, Hindi", "currentLoad": 1, "status": "Available", "persona": "Empathetic, soft-spoken, reflective" },
  { "id": "VOL_006", "name": "Tom K.", "accred": 3, "specialties": "Suicidal Ideation, Veterans", "language": "English", "currentLoad": 5, "status": "Busy", "persona": "Composed, grounded, decisive" }
]
```

✅ PASS: returns ONLY a ```json``` block with `"volunteerId": "VOL_003"` (load 1, the lowest among eligible).
❌ FAIL — picks VOL_001 instead: load-balancing rule isn't dominant. In the prompt, change "PRIMARY RULE" to be even louder, e.g. "LOWEST currentLoad WINS over every other consideration."
❌ FAIL — picks VOL_002 or VOL_006: Busy / load≥4 filter isn't firing. Strengthen the hard constraints.
❌ FAIL — returns conversational text before/after the JSON: add "Output ONLY the JSON code block. No prose."

### Test 2 — Don't over-resource on Low-risk
Same pool, change to:
```
RiskLevel: Low
Language: English
PersonaNotes: Coping but a bit lonely.
PreferredVolunteerStyle: Gentle, attentive listener
```

✅ PASS: picks a tier-1 volunteer (general accreditation), NOT a tier-3 — even though tier-3 volunteers might have lower load. The pool above doesn't include tier-1s, so add one for this test: `{"id":"VOL_005","name":"Aroha W.","accred":1,"language":"English, Te Reo","currentLoad":0,"status":"Available","persona":"Gentle, attentive listener"}` → should pick VOL_005.

### Test 3 — No-match (escalation path)
```
RiskLevel: High
Language: Arabic
PersonaNotes: Test.

Volunteer pool: [the pool from Test 1]
```

✅ PASS: returns the no-match JSON shape with `volunteerId: null` and a `reason` explaining no volunteer satisfies the constraints.

### Test 4 — Busy filter overrides load
Add to Test 1's pool: `{"id":"VOL_999","name":"Test","accred":3,"language":"English","currentLoad":0,"status":"Busy","persona":"x"}`

✅ PASS: does NOT pick VOL_999 despite load=0. The `Busy` status is a hard exclusion.

---

## 7. Capture the agent endpoint URL

In Foundry → your Agent 2 → **Endpoint** tab (or similar). Copy the
**OpenAI Responses URL** — looks like:

```
https://<your-resource>.services.ai.azure.com/api/projects/<project>/agents/Agent2/endpoint/protocols/openai/v1/responses
```

Open `.env` in your workspace and paste it into `AGENT2_URL=`.

```
AGENT2_URL=https://lakeMacSPN.services.ai.azure.com/api/projects/lakeMacSPN-agent/agents/Agent2/endpoint/protocols/openai/v1/responses
```

Then restart the proxy (`python proxy_server.py`) so it picks up the new env value.

---

## 8. Done

Once all four tests pass, move on to wiring the HTML portal in live
mode. The proxy will accept POST /api/agent2/match calls and the
portal's "Find First-Call Volunteer" button will hit a real agent
instead of the JS mock.
