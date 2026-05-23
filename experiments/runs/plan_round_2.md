# Round 2 — Add structured output format to main agent

## Current state
- Baseline RACE: 4.20 (COMP=3.80, DEPTH=3.80, INST=4.60, READ=4.60)
- Best commit: 14a1c5f (Round 1 baseline)

## Data analysis

Per-case scores:
| case | RACE | C | D | I | R |
|------|------|---|---|---|---|
| drb_en_60 (cislunar SSA) | 4.50 | 4 | 4 | 5 | 5 |
| drb_en_64 (UAV PID) | 4.50 | 4 | 4 | 5 | 5 |
| drb_en_68 (K8s autoscaling) | 3.50 | 3 | 3 | 4 | 4 |
| drb_en_95 (Diamond Sutra) | 5.00 | 5 | 5 | 5 | 5 |
| drb_en_100 (AI social relations) | 3.50 | 3 | 3 | 4 | 4 |

Bottleneck: COMP=3.80 and DEPTH=3.80 are the weakest dimensions.
INST=4.60 and READ=4.60 are already strong — no need to target those.

Judge rationales for the two weak cases:
- drb_en_68: "lacks depth on non-elastic node groups, business metric integration,
  and limitations of each approach"
- drb_en_100: "lacks breadth on the full spectrum of AI technologies (e.g., social
  robots, virtual assistants)" + missing deeper trade-off analysis

Root cause: the current main agent prompt has NO output structure requirements.
It just says "write the final answer." Without guidance, the model writes a
solid intro but skips analysis, trade-offs, and limitations sections — exactly
what DEPTH scores measure.

## Candidate levers

1. **Add structured output format to main agent** (Findings + Analysis +
   Limitations). Forces depth by requiring explicit sections. Expected: DEPTH ↑
   0.3–0.5. Cost: zero tokens overhead. **← CHOSEN**

2. **Increase subagent calls from "once or twice" to 2–3**. More angles =
   higher COMP. Cost: +30–50% LLM calls. Defer — try cheaper structural
   fixes first.

3. **Add outline/planner step before subagent dispatch**. Systematically
   covers all sub-topics mentioned in the question. Expected: COMP ↑ 0.4.
   Cost: +1 LLM call per case. Defer — higher complexity.

4. **More search calls per subagent (1–2 → 2–3)**. More evidence = better
   COMP. Cost: +Tavily $$ + LLM tokens. Defer.

## Choice + reason
Lever 1. It is the smallest possible change (one prompt block addition) that
directly targets the measured gap (DEPTH=3.80). Levers 2–4 all cost more
tokens and may interfere with the clean baseline signal; they are deferred
until we confirm Lever 1's impact.

## Specific change
In `deepresearch_agent.py::_main_agent_prompt`, add an output format block
after the workflow steps, requiring:
- ## Findings — covering key sub-topics
- ## Analysis — causes, trade-offs, boundary conditions
- ## Limitations — evidence gaps and caveats

## Success criteria
- RACE mean > 4.25 (improvement > IMPROVEMENT_THRESHOLD of 0.05).
- DEPTH mean > 3.80 (the primary target dimension).
- COMP may also rise if structured sections prompt more thorough coverage.
