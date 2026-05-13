# NGM Referral Pipeline — Live Mode Quickstart

Run the HTML portal against your real Foundry agents. Five-minute setup.

---

## What you have in this folder

| File                                 | Purpose                                                  |
|--------------------------------------|----------------------------------------------------------|
| `Hospital_Intake_Portal.html`        | The portal. Open in a browser. Includes login / kanban / volunteer view. |
| `proxy_server.py`                    | Flask proxy (browser → proxy → Foundry). Holds API key.  |
| `test_agent1.py`                     | One-shot connectivity test for Agent 1.                  |
| `.env` / `.env.example`              | Credentials. `.env` is git-ignored.                      |
| `requirements.txt`                   | Python deps for the proxy.                               |
| `Agent1_Foundry_Setup.md`            | What to paste into Agent 1's Instructions in Foundry.    |
| `Agent2_Foundry_Setup.md`            | Same, for Agent 2.                                       |
| `Agent1_Build_Walkthrough.md`        | Click-by-click for Agent 1 build.                        |
| `Agent2_Build_Walkthrough.md`        | Click-by-click for Agent 2 build.                        |
| `Volunteers_Registry.xlsx/.csv`      | Volunteer seed data.                                     |
| `User_Referrals.xlsx/.csv`           | User seed data.                                          |

---

## 1. One-time setup

```bash
cd /path/to/Hackathon_NGM
pip install -r requirements.txt
cp .env.example .env          # if you don't already have .env
# edit .env — set AGENT1_URL, AGENT2_URL, FOUNDRY_API_KEY
```

For your project, the Agent 1 URL pattern is:
```
https://lakeMacSPN.services.ai.azure.com/api/projects/lakeMacSPN-agent/agents/Agent1/endpoint/protocols/openai/v1/responses
```

Agent 2 will use the same pattern with `/agents/Agent2/` once you build it.

---

## 2. Verify the endpoint works

Before launching the full stack, hit Agent 1 once to make sure your
endpoint and key are good:

```bash
python test_agent1.py
```

Expected: `✓ Agent replied: <short greeting>`. If you get HTTP 401/403,
your key or URL is wrong. If you get HTTP 404, double-check the agent
name in the URL matches what's in Foundry (case-sensitive).

---

## 3. Start the proxy

```bash
python proxy_server.py
```

You should see:
```
NGM proxy listening on http://127.0.0.1:5000
  Agent 1 URL: https://lakeMacSPN…/agents/Agent1/…
  Agent 2 URL: (NOT SET — Agent 2 calls will 500)   ← until you build it
  Key:         set
```

Leave this terminal running. Open a second terminal/browser tab for
the next step.

---

## 4. Open the portal

Open `Hospital_Intake_Portal.html` in your browser (double-click works,
or `open Hospital_Intake_Portal.html` on macOS).

1. Login screen → pick **Hospital Staff** (or **Admin** if you want override + roster-edit powers).
2. Top-right gear icon → toggle **Use Live Foundry Agents** ON, click **Test connection** to verify, **Save**.
3. The connection badge in the header should turn green: **Live (A1 only)** until you wire Agent 2, then **Live (A1+A2)**.
4. Click **+ New Hospital Referral**, fill the form, submit.
5. On the user detail modal, click **Run Induction** — a live chat opens. Type as the user; the agent responds via Foundry. When the agent emits its JSON block, the portal saves the persona and shows you the matchmaker step.

---

## 5. Roles in the portal

| Role          | What they see                                                                  |
|---------------|--------------------------------------------------------------------------------|
| **Hospital**  | Intake form, pipeline kanban/table, can run agents.                            |
| **Admin**     | All of the above + volunteer roster inline-edit, **Override** match button on each user, "view as volunteer" shortcuts, reset/export controls. |
| **Volunteer** | Demo screen showing the volunteer's next assignment and recent calls. Logged in as Sarah J. (VOL_001) by default, or whichever volunteer the Admin selected via "view as". |

Logout from the top-right at any time to switch roles.

---

## 6. The two view modes

The dashboard has a **Kanban / Table** toggle.

**Kanban** is the recommended demo view — 5 columns matching the pipeline stages (Awaiting Induction → Awaiting Match → First Call Booked → Second-Call Decision → Completed). Each user is a card. Click a card to drill in.

**Table** is the same data flat — useful for admin auditing.

---

## 7. Troubleshooting

### "Proxy unreachable" (red dot)
Proxy isn't running, or running on a different port. Run `python proxy_server.py` and check Settings → Proxy URL matches.

### "Live (A1 only)" — Agent 2 calls fail
You haven't built Agent 2 in Foundry yet, or `AGENT2_URL` is missing in `.env`. Follow `Agent2_Build_Walkthrough.md`, then restart the proxy.

### Agent 1 chat hangs / times out
Check the proxy terminal output. The OpenAI Responses API call body might be wrong for your Foundry tenant — some tenants want `{"input": "..."}` (current), others want `{"messages": [{"role":"user","content":"..."}]}`. If you see HTTP 400 in the proxy logs, edit `proxy_server.py` and try the messages form.

### "Foundry rejected the request" (HTTP 401/403)
API key is wrong, expired, or has a trailing whitespace. Re-copy from Foundry → Project settings → Keys and Endpoint.

### CORS error in browser console
The proxy uses `flask-cors` which allows all origins. If you still get CORS errors, you might be hitting the Foundry URL directly from the browser — make sure your Settings → Proxy URL points at the proxy (127.0.0.1:5000), not the Foundry endpoint.

### Mock fallback
If a live call fails mid-conversation, the portal falls back to the deterministic JS mock so the demo keeps moving. Look for the connection badge — it'll go red, and you'll see a fallback message in the chat.

---

## 8. Demo flow for judges

1. Land on login screen. Pick **Hospital Staff**.
2. **+ New Hospital Referral** → fill in a high-risk user.
3. Click the new card on the Kanban board.
4. **Run Induction** opens the live chat. Role-play the user for 3–4 turns.
5. When Agent 1 emits its persona JSON, the user moves to "Awaiting Match" in the kanban.
6. Click **Find First-Call Volunteer**. Agent 2 picks the lowest-load eligible volunteer.
7. **Log First-Call Outcome** with engagement level → second-call bot decides who calls next.
8. Logout → log in as **Admin** to show roster editing and the override button.
9. Logout → log in as **Volunteer (demo)** to show what a volunteer sees on their end.
10. Top-right **Crisis: Lifeline 13 11 14** button — show the safety guardrail is always one tap away.

### When judges ask "is this scalable?"
The agents are stateless. The Excel/CSV files are demo seeds, not the
production store. To swap localStorage for SQL or Cosmos DB, we change
one function in `Hospital_Intake_Portal.html` and zero things in the
agents themselves.

### When judges ask "how do you keep it safe?"
- Agent 1's system prompt has a SAFETY section that overrides every
  other instruction when self-harm language is detected.
- The portal independently scans every form submission for the same
  trigger phrases.
- The Lifeline modal is always one click away in the header.
- Every Persona that triggers the guardrail is marked SAFETY ESCALATION
  and excluded from auto-matching.

---

## 9. Rotate the API key after the demo

The key currently in `.env` was shared in chat. Once the hackathon
ends, go to Foundry → Project settings → Keys and Endpoint → Rotate.
Paste the new key into `.env` and restart the proxy.
