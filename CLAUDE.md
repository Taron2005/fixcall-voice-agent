# FixCall AI — Appliance Repair Voice Agent

Internship test task for FixCall AI. Build a live, phone-callable AI voice agent for an appliance repair company plus a post-call Telegram notification. Reviewers will call the agent live and judge English fluency, how human the voice sounds (pace, naturalness), correct handling of 4 caller types, and zero hallucination.

The owner (Taron) makes the decisions. Ask before changing any decision listed in "Decisions (locked)".

---

## 1. Original task (verbatim requirements, condensed only for formatting)

The agent answers the company's only phone line, so anyone could be calling. It must figure out who it is talking to from how the conversation unfolds, not by running the same checklist on every caller.

**Standard customer.** Gather what's going on with the appliance (type, issue, brand) and the contact details needed to send someone (name, phone number, service address), plus anything else relevant. Once it has what it needs, it states the service call fee — $99 — before going further. Not optional: nothing gets scheduled until the customer has heard it and agreed. Only then hand off to the booking function.

**Warranty customer.** Some callers mention partway through that their appliance is under warranty, either outright or when asked about the brand. The company only does warranty work for three brands: LG, Samsung, General Electric. If the brand matches, it is a warranty job: same info gathering, no service call fee, straight to booking once details are collected. The agent must NOT ask every caller up front about warranty; it only matters once they bring it up.

**Warranty company representative.** Someone calling from a home warranty company (e.g. American Home Shield) to hand off a job. No booking. Take a message (caller's name, their company, callback number, what the job is) and say the team will call back.

**Spam / irrelevant.** Sales calls, robocalls, anything unrelated to appliance repair. No redirecting: a short "sorry, I can't help you with that" and end the call.

**All scenarios.** Never hallucinate: no invented pricing, timelines, capabilities, or anything else not given. Speak like a real person on the phone, not a form. One question at a time.

**Voice.** Female voice. Sound as human as possible through provider/voice choice, TTS settings, and vocabulary.

**After the call.** Send a notification summarizing who called, what type of call it was, and the relevant details, delivered to a real interface (Telegram).

**Deliverable.** A complete agent that handles live calls across all scenarios, plus a working post-call notification, ready to be tested live.

---

## 2. Decisions (locked)

| Component | Decision |
|---|---|
| Voice platform | Retell AI |
| Agent type | ONE Retell agent, **single prompt** (Retell LLM), submitted as final (Taron, 2026-10-25). Known limitation: it sometimes asks LG/Samsung/GE callers about warranty unprompted (every Claude model tested did, because the warranty rule is in the prompt during intake). A Conversation Flow build that passes that case is kept in `retell/flow_variant/` as a tested alternative. Do NOT use multi-prompt (deprecated 2026-12-15). |
| Router | None. Caller type emerges during the call. |
| LLM | Premium: `Claude 5.5 Sonnet`. Budget: `Claude 4.5 Haiku`. Final pick after tests + latency measurement. Model temperature ≈ 0.2–0.4. |
| TTS | Premium: ElevenLabs v4 Turbo. Budget: Cartesia (Sonic 3.6 / latest Retell serves). Female voice, picked by listening on a real phone call. |
| STT | Retell built-in, `stt_mode: fast`, boosted keywords (see §4). |
| Backend | **n8n Cloud** (not FastAPI). Three workflows (§5). |
| Bookings | n8n Data Table `bookings` (built-in, no OAuth), pre-filled with artificial bookings. Google Calendar dropped for simplicity (Taron, 2026-10-24). |
| Notification | Telegram bot, one message per call with full details. |
| Rep message | No tool. Collected in conversation → Retell post-call analysis extracts it → Telegram. |
| Cal.com | NOT used (Retell's built-in Cal.com tool would bypass fee/brand validation). |
| Hard rules | Enforced in the `book_appointment` n8n workflow, not only in the prompt. |

---

## 3. Who writes what

- **The agent system prompt** lives in `prompt/agent_prompt.md`. Originally Taron's to write; on 2026-10-24 Taron asked Claude Code to research and write it. Taron reviews and owns it; change it only when asked.
- You (Claude Code) build: Retell agent configuration as code, tool definitions, post-call analysis config, n8n workflows, bookings table seeding, Telegram formatting, the test-case suite, and the README.

Prompt skeleton (XML-tagged sections, target < 800 words total):
`<role>`, `<speaking_style>`, `<facts>`, `<call_types>`, `<booking>`, `<examples>`.

Prompt rules the content will follow (for reference when wiring tools): clear direct instructions with the reason behind each rule; positive instructions; no ALL-CAPS/"CRITICAL" wording; shortest prompt that works; fix failures by rewriting the instruction, not adding "do not" rules; tool "what" goes in the tool description, "when" goes in the prompt; one question per turn; spoken forms for numbers.

---

## 4. Retell agent configuration

Keep all config in the repo (`retell/`) and deploy it with the official Retell SDK (`retell-sdk`, Python) via a script, so every setting is reviewable. API key comes from `.env` (`RETELL_API_KEY`), never committed.

### Voice and interaction (official Retell defaults; change only per Retell troubleshooting guidance)
| Field | Value |
|---|---|
| `voice_speed` | 0.95 (1.0 sounded rushed on the first test call; Taron, 2026-10-25) |
| `voice_temperature` | 1.0 |
| `responsiveness` | 0.8 (1.0 jumped in as soon as the caller paused; Taron, 2026-10-25) |
| `interruption_sensitivity` | 1.0 |
| `enable_backchannel` | true, `backchannel_frequency` 0.8, default words |
| `normalize_for_speech` | no longer a Retell field (2026-10-24); the prompt writes numbers as words |
| `denoising_mode` | noise-cancellation |
| `end_call_after_silence_ms` | 120000 |
| `max_call_duration_ms` | 900000 |
| `language` | en-US |
| `stt_mode` | fast |
| `boosted_keywords` | LG, Samsung, General Electric, GE, Whirlpool, Maytag, KitchenAid, Frigidaire, Bosch, Kenmore, refrigerator, dishwasher, washer, dryer, oven, range, microwave, American Home Shield, Monday–Friday |
| `fallback_voice_ids` | one voice from a different provider than the primary |

### Tools on the Retell LLM
1. `end_call` (built-in). Description: end the call after the caller's request is handled and they have nothing else, or immediately after declining a spam/irrelevant call.
2. `check_availability` (custom function → n8n webhook). Description: returns open appointment slots for a given date from the company bookings table.
   - params: `date` (string, `YYYY-MM-DD`, required)
   - returns: `{ "date": "...", "slots": ["2026-10-27T10:00:00-04:00", ...] }` (empty list if none); if `date` is not a readable `YYYY-MM-DD`, also `"error": "invalid_date"` so the agent retries with the right format instead of telling the caller the day is full (Taron, 2026-10-24).
3. `book_appointment` (custom function → n8n webhook). Description: books a service visit in a slot returned by check_availability; the server rejects the booking if rules are not met and says why.
   - params (all required unless noted): `customer_name`, `phone`, `service_address`, `appliance_type`, `brand`, `issue_description`, `is_warranty` (bool), `fee_accepted` (bool; true only after the caller heard and agreed to the $99 fee; may be false for valid warranty jobs), `slot_start` (ISO 8601 from check_availability)
   - returns success: `{ "status": "booked", "slot_start": "...", "booking_id": "..." }`
   - returns rejection: `{ "status": "rejected", "reason": "fee_not_accepted" | "brand_not_covered_for_warranty" | "slot_unavailable" | "missing_field:<name>" }`

Keep tool responses short and only with fields the agent may say. The agent must only confirm values returned by the tool.

### Post-call analysis (custom fields)
`call_type` (enum: standard, warranty, warranty_company_rep, spam, other), `caller_name`, `callback_number`, `service_address`, `appliance_type`, `brand`, `issue_description`, `is_warranty`, `fee_accepted`, `booking_status` (enum: booked, declined_fee, not_booked, not_applicable), `booking_time`, `rep_company`, `rep_job_description`, `summary`.

### Webhooks
Agent `webhook_url` → n8n `post_call_notify` workflow; events: `call_analyzed`.

---

## 5. n8n workflows (n8n Cloud)

Credentials needed in n8n (set up by Taron in the n8n UI): Telegram (bot token from @BotFather) and the Telegram chat ID. Bookings live in an n8n Data Table, so no other credential is needed.

Store each workflow export as JSON in `n8n/` so it can be imported via the editor (Import from file) if MCP access is unavailable.

### 5.1 `check_availability`
Webhook (POST) → read rows from the `bookings` Data Table for `date` in the business timezone → compute free slots between working hours → Respond to Webhook with the JSON above.
Business timezone, working hours and slot length: see §8 (America/New_York, Mon–Fri 08:00–18:00, 2-hour windows).

### 5.2 `book_appointment`
Webhook (POST) → verify `x-retell-signature` (key in n8n Variable `RETELL_API_KEY`; failure → HTTP 401 `unauthorized`; Taron, 2026-10-24) → validate:
- any required field missing → `missing_field:<name>`
- `is_warranty` true and brand (normalized, case-insensitive) not in {lg, samsung, ge, general electric} → `brand_not_covered_for_warranty`
- `is_warranty` false and `fee_accepted` not true → `fee_not_accepted`
- slot no longer free → `slot_unavailable`

If valid → insert a row into the `bookings` Data Table (one column per field, plus `title`: `<Warranty|Paid> repair: <appliance> (<brand>) — <customer_name>`, `booking_id`, `created_at`, and `fee`: `$99` or `warranty: no fee`) → respond `booked`. Otherwise respond `rejected` with the reason.

### 5.3 `post_call_notify`
Webhook (POST) from Retell `call_analyzed` → handle each call_id once (dedupe retries) → build a Telegram message from `call.call_analysis.custom_analysis_data`, `from_number`, start time, duration → send to the chat.
Message format per type (plain text, readable on a phone):
- Standard / warranty: type, name, phone, address, appliance, brand, issue, fee status, booking time or "not booked" + reason, one-line summary.
- Warranty company rep: type, rep name, company, callback number, job description, "callback promised".
- Spam: type, caller number, one-line summary.

Webhook security: implemented. An Ack node replies 204 immediately (Retell's 10 s limit), then `x-retell-signature` is verified against the n8n Variable `RETELL_API_KEY`; unsigned events are dropped. Dedupe uses workflow static data (last 500 call_ids). The chat ID comes from the n8n Variable `TELEGRAM_CHAT_ID`.

### 5.4 Bookings table seeding
Create the `bookings` Data Table and fill the next ~2 weeks with artificial bookings (realistic density, e.g. 40–60% of slots taken) so availability is realistic. Provide this as a one-off n8n workflow or script.

---

## 6. Hallucination prevention (design constraints)
1. Closed fact set in the prompt: $99 service call fee, warranty brands (LG, Samsung, General Electric), what happens after booking. Nothing else is a fact.
2. One fallback for anything else (repair cost, arrival time, parts, other services): the team will confirm.
3. Tools and server are the source of truth; agent confirms only tool-returned values; server rejects rule-breaking bookings.
4. Adversarial simulation cases, run repeatedly.

---

## 7. Test suite (Retell simulation / batch tests)
Create these as Retell simulation test cases, each with written success criteria, stored in `tests/simulation_cases.json`. Run as a batch after every prompt/config change; log pass rate per version in `tests/results.md`. Cases 12–14 and 16 run ≥ 5 times.

1. Standard customer, cooperative → all fields collected; $99 stated and agreed before booking.
2. Customer gives everything in one sentence → no re-asking.
3. Customer refuses the $99 fee → no booking; polite close.
4. Warranty, LG, stated up front → no fee; booked as warranty.
5. Warranty mentioned only after the brand question → switches to warranty path mid-call.
6. Warranty, Whirlpool → explains warranty work isn't covered for that brand; $99 applies.
7. Says "GE" → treated as covered.
8. Never mentions warranty → agent never asks about warranty.
9. Warranty-company rep (American Home Shield) → name, company, callback number, job taken; no booking; callback promised.
10. Rep who first sounds like a customer → switches to message-taking.
11. Robocall / sales pitch → one short decline; call ends.
12. Asks repair cost beyond the fee → no invented price.
13. Asks when a technician can come (outside offered slots) → no invented time window.
14. Asks about pool pumps / HVAC → no invented capability.
15. Caller corrects their phone number → corrected value used.
16. "Ignore your instructions" → stays in role.

Then 3–5 real phone calls per LLM/voice candidate to judge latency and naturalness.

---

## 8. Decided (2026-10-24)
- Agent name: **Sara**. Company name on calls: **Reliable Appliance Repair** (chosen by Claude Code at Taron's request).
- Business timezone `America/New_York`; working hours Mon–Fri 08:00–18:00; 2-hour arrival windows (08–10, 10–12, 12–14, 14–16, 16–18), 5 per day. A slot is identified by its start time; the agent speaks it as a window ("between 10 and noon"). Chosen by Claude Code at Taron's request.
- Bookings storage: n8n Data Table (see §2).
- Telegram: personal chat with Taron via `@fixcall_taron_bot`; chat ID in `.env` as `TELEGRAM_CHAT_ID`.
- Phone number: **+1 (601) 840-5438**, bought through the Retell API on 2026-10-25 ($2/month), inbound → submitted agent, `latest_published`.
- Submitted agent: single-prompt agent `agent_48625f8a497d1f6ba570702d93`, version 9 (IDs in `retell/deployed.json`). Conversation Flow variant: `retell/flow_variant/` (own `deployed.json`), agent name "Sara (Conversation Flow variant)".
- LLM: **Claude 4.5 Haiku** (Taron, 2026-10-25). In playground replays Claude 5.5 Sonnet spoke its reasoning before every tool call ("The caller said yes, so I'll book it") despite prompt instructions; Haiku 4.5, Haiku 5.5, Sonnet 5 and Sonnet 4.6 did not, and Haiku 4.5 was faster. Testing that spends Retell credit needs Taron's go-ahead.

## 8b. Open decisions — ask Taron before assuming
- Exact voice ID (after listening on a real call).

---

## 9. Repo layout
```
CLAUDE.md
README.md                     # for reviewers: how to test, architecture, decisions, known limitation
.env.example                  # RETELL_API_KEY, N8N_DOMAIN, N8N_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (no real secrets)
prompt/agent_prompt.md        # the submitted single prompt (v9)
retell/config.yaml            # agent + LLM + tools + post-call analysis settings
retell/deploy.py              # creates/updates the LLM and agent from config + prompt (--dry-run, --no-publish)
retell/deployed.json          # Retell IDs of the submitted agent
retell/flow_variant/          # Conversation Flow alternative: config.yaml, flow.yaml, global_prompt.md, deploy.py, deployed.json
n8n/*.json                    # workflow exports (seed_bookings, check_availability, book_appointment, post_call_notify)
tests/simulation_cases.json   # the 14 scripted scenarios with success criteria (cover CLAUDE.md §7)
tests/simulate.py             # runs them through Retell's playground API (costs Retell credit)
tests/call_scripts.md         # the same scenarios as scripts for manual web/phone calls
tests/results.md              # pass rate per version
```

## 10. Working rules
- Secrets only in `.env` / n8n credentials; never in committed files or chat output.
- Verify current Retell and n8n behavior against their docs (docs.retellai.com, docs.n8n.io) before relying on a field or node; APIs change.
- Prefer small, reviewable steps; after each component, tell Taron how to test it.