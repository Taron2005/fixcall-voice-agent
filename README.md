# Sara — AI receptionist for Reliable Appliance Repair

A phone-callable voice agent that answers an appliance repair company's only line, works out who is calling, and handles four caller types: standard customers, warranty customers, home-warranty-company representatives, and spam. After every call, a summary lands in Telegram.

## Call it

**Phone number: +1 (601) 840-5438** (Retell-provisioned US number; every inbound call goes to the latest published version of the agent below).

Without a phone number you can still talk to it in the browser: Retell dashboard → Agents → **"Sara - Reliable Appliance Repair"** → Test → Web Call. Browser calls have no caller ID, so "use the number I'm calling from" makes Sara ask for a number instead.

Ready-made scripts for every scenario are in [tests/call_scripts.md](tests/call_scripts.md).

## What happens on a call

| Caller | What Sara does |
|---|---|
| Standard customer | Collects appliance, problem, brand, name, phone and address one question at a time; states the **$99 service call fee** and waits for a yes; checks the calendar; reads the details back once; books. |
| Warranty customer (says so) | LG, Samsung or GE: same details, **no service call fee**, straight to booking. Other brands: explains warranty work covers only those three, so it would be a regular $99 visit. |
| Home warranty company rep (e.g. American Home Shield) | Takes a message (name, company, callback number, job details), reads the number back, promises a callback. No booking. |
| Sales call, robocall, unrelated | "Sorry, I can't help you with that." and hangs up. |

Anything Sara has no fact for (repair price, parts, exact arrival time, repair length) gets "the team will confirm", never a guess.

## Architecture

```
Caller ──► Retell (STT → Claude 4.5 Haiku → ElevenLabs TTS)
              │  tools (HTTPS, signed with x-retell-signature)
              ├──► n8n check_availability ──► n8n Data Table "bookings"
              ├──► n8n book_appointment  ──► validates hard rules ──► Data Table
              └──► after the call: call_analyzed webhook ──► n8n post_call_notify ──► Telegram bot
```

- **Retell AI**: telephony, speech-to-text, the LLM and text-to-speech. Agent configuration lives in [retell/config.yaml](retell/config.yaml) and the prompt in [prompt/agent_prompt.md](prompt/agent_prompt.md); [retell/deploy.py](retell/deploy.py) deploys both with the official SDK, so every setting is reviewable.
- **n8n Cloud**: three webhook workflows, exported in [n8n/](n8n/).
  - `check_availability`: free two-hour windows for a date (Mon–Fri, 8 AM–6 PM Eastern).
  - `book_appointment`: the server-side rulebook. It rejects a booking if a field is missing, a warranty job is for a non-covered brand, a paid job has no accepted fee, or the slot is taken, and tells Sara why.
  - `post_call_notify`: one Telegram message per call (deduplicated across Retell retries), formatted per caller type.
- **Bookings** are stored in an n8n Data Table, pre-filled with fake bookings ([n8n/seed_bookings.json](n8n/seed_bookings.json)) so availability looks real.
- **Security**: the booking and post-call webhooks verify Retell's HMAC signature, so only Retell can create bookings or notifications. Keys live in `.env` and n8n Variables, never in the repo.

## Key decisions and why

| Decision | Why |
|---|---|
| Single Retell agent, no router | The caller type emerges from the conversation, as the task asks. |
| **Claude 4.5 Haiku** | Claude 5.5 Sonnet spoke its tool-call reasoning out loud ("The caller said yes, so I'll book it"). Haiku 4.5 didn't in any replay, and it answers faster. |
| ElevenLabs "Grace" (v4 Turbo), Cartesia fallback | Natural female US voice; voice speed 0.95 and responsiveness 0.8 after test calls felt rushed. |
| Closed fact set in the prompt | Sara may state only the $99 fee, the warranty brands, the visit hours and what happens after booking. Everything else is "the team will confirm". |
| Hard rules enforced in n8n, not only in the prompt | Even if the model slips, a booking without an agreed fee, with a non-covered warranty brand, or in a taken slot cannot be saved. |
| Tools return only what Sara may say | She confirms only the window the booking tool returned. |

## Known limitation: unprompted warranty question

The task says Sara must not ask callers about warranty unless they bring it up. The submitted agent mostly follows that, but **when a caller names LG, Samsung or GE, it sometimes asks "Is it under warranty?"** on its own.

This is not a wording problem we could prompt away. We tested five prompt variants on Claude 4.5 Haiku and the same prompt on Claude 5.5 Haiku, Sonnet 5 and Sonnet 4.6: every one asked in most runs, because the warranty rule is visible to the model during intake and it reasons that the fee depends on it. The server still keeps bookings correct, but the question itself breaks the rule.

**Tested fix, not submitted:** a Retell **Conversation Flow** build in [retell/flow_variant/](retell/flow_variant/) (agent "Sara (Conversation Flow variant)"). Its intake and fee steps contain no warranty instructions at all; a separate warranty step is entered only when the caller says "warranty". It passed all 14 test scenarios, including this one. It was not chosen as the final agent because a fixed flow is less flexible when a caller goes off-script.

## Testing

- [tests/simulation_cases.json](tests/simulation_cases.json): 14 scenarios covering the 16 cases in the brief, each with success criteria.
- [tests/simulate.py](tests/simulate.py): plays a scripted caller against the agent through Retell's playground API with mocked tools and checks the hard rules automatically (`.venv/bin/python tests/simulate.py 1 8`). It spends Retell credit.
- [tests/results.md](tests/results.md): pass rate per version. The submitted agent's last full run (version 7) passed 12 of 14: one was a double confirmation, fixed in version 8, and the other is the warranty question above.

## Run it yourself

1. `cp .env.example .env` and fill in the keys (Retell, n8n, Telegram).
2. In n8n: import the four workflows from `n8n/`, add a Telegram credential and the Variables `RETELL_API_KEY` (the Retell key with the webhook badge) and `TELEGRAM_CHAT_ID`, create the `bookings` Data Table, run "Seed bookings table" once, then publish the other three workflows.
3. `python3 -m venv .venv && .venv/bin/pip install retell-sdk pyyaml python-dotenv httpx`
4. `.venv/bin/python retell/deploy.py` creates or updates and publishes the agent (`--dry-run` to preview).
5. Buy a US number in Retell and set the agent as its inbound agent.
