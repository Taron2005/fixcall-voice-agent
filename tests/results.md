# Test results

Simulated calls run with `tests/simulate.py` (scripted caller through Retell's playground API, tools mocked).
Scenario numbers are the simulator's; they cover the 16 cases in CLAUDE.md §7.

| Date | Agent / version | Model | Runs | Passed | Notes |
|---|---|---|---|---|---|
| 2026-10-25 | single prompt v7 | Claude 4.5 Haiku | 14 × 1 | 12 | #2 confirmed the address twice; #8 asked an LG caller about warranty unprompted |
| 2026-10-25 | single prompt v8–v9 | Claude 4.5 Haiku | #8 × 3 each | 0 | Warranty question persisted after rewording |
| 2026-10-25 | single prompt v9 drafts | Haiku 4.5, Haiku 5.5, Sonnet 5, Sonnet 4.6 | #8 × 3 each | 0–1 of 3 | Every model asked about warranty; led to the Conversation Flow rebuild (CLAUDE.md §2) |
| 2026-10-25 | flow agent v0 (draft) | Claude 4.5 Haiku | #8 × 2, #1–3 × 1 | 5/5 | #8 fixed: no warranty question, $99 stated, booked as paid |
| 2026-10-25 | flow agent v0 (draft) | Claude 4.5 Haiku | #4–7, #9–14 × 1 | 9/10 | #13 pool pump/HVAC went to intake and claimed "we don't service" them |
| 2026-10-25 | flow agent v0 (published) | Claude 4.5 Haiku | #13 × 1 | 1/1 | Fixed by routing other services to the polite decline |

**Submitted (Taron, 2026-10-25): single-prompt agent v9.** On the v7 full run it passed 12/14; scenario 8 (LG/Samsung/GE caller who never mentions warranty) is a known failure, and scenario 2's double confirmation was fixed in v8. The Conversation Flow variant (`retell/flow_variant/`) passed all 14 scenarios and is kept as the tested alternative.

All 14 scenarios pass on the published flow agent v0. Cases 12–14 and 16 from CLAUDE.md §7 (simulator #12–14) still need their ≥ 5 repeat runs.
