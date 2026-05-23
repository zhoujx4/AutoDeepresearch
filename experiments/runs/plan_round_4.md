# Round 4 — Explicitly diversify subagent scope to cover named sub-topics

## Current state
- Best RACE: 4.25 (Round 3) — not "improved" (at threshold), best score from baseline=4.20
- Dimension means R3: COMP=3.80, DEPTH=4.00, INST=4.40, READ=4.80

## Data analysis (Round 3 per-case)

| case | R1 | R3 | Δ | key gap |
|------|----|----|---|---------|
| drb_en_60 (cislunar) | 4.50 | 4.50 | = | none |
| drb_en_64 (UAV PID) | 4.50 | 4.00 | ↓ | "lacks H-inf, SMC, relay feedback, comparative analysis" |
| drb_en_68 (K8s auto) | 3.50 | 4.50 | ↑ | fixed by more searches |
| drb_en_95 (Diamond) | 5.00 | 5.00 | = | perfect |
| drb_en_100 (AI social) | 3.50 | 3.25 | ↓ | "lacks social robots, virtual assistants, social media algorithms" |

Root cause of remaining gaps:
- The agent calls 2-3 subagents but doesn't *differentiate their scope*.
- Both subagents end up searching similar query angles (main topic), missing
  specific named methods (H-infinity control, SMC) or tech categories (social
  robots, virtual assistants).
- Each subagent must target a distinct NAMED sub-topic area of the question.

## Candidate levers

1. **Explicit scope differentiation in main agent prompt** — instruct the main
   agent to target different named aspects per call (e.g., traditional vs modern
   methods; specific tech categories vs psychological effects). Hypothesis:
   COMP↑ 0.3-0.5 for the two weak cases. Cost: zero tokens, prompt-only.
   **← CHOSEN**

2. **Question decomposition node** — add a new LangGraph node that explicitly
   decomposes the question into sub-topics before dispatching subagents. More
   structured but higher complexity. Defer — try prompt change first.

3. **Pass must-cover hints from source_notes to main agent** — the dataset has
   `source_notes` already passed in, but the main agent ignores them for search
   direction. If they contained topic hints, this could help. Currently
   source_notes are just task metadata. Not useful for this dataset. Defer.

## Choice + reason
Lever 1. The simplest change: one directive in the main agent prompt telling it
to *explicitly diversify* what each subagent researches. If the main agent targets
"traditional control methods" vs "AI/ML approaches" vs "implementation aspects"
for a UAV PID question, H-infinity and SMC have a much better chance of being found.

## Specific change
In `_main_agent_prompt`, update step 1:
  Add: "Each subagent call must target a clearly different named aspect of the
  question (e.g., one for foundational theory, one for specific named methods
  or technologies, one for practical implementation or trade-offs). Do not let
  two subagents cover the same angle."

## Success criteria
- RACE mean > 4.30 (beats best score of 4.25 by >0.05 → "improved").
- COMP mean > 3.80 (close the named-topic gap).
- INST mean ≥ 4.40 (no regression).
