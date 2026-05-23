# Round 8 — Deepen subagent search angles + richer synthesis depth

## Current state
- Best RACE: 4.70 (Round 7, status=improved)
- Dimension means R7: COMP=4.40, DEPTH=4.40, INST=5.00, READ=5.00

## Data analysis

Round 7 per-case:
| case | RACE | C | D | I | R | vs R6 |
|------|------|---|---|---|---|-------|
| drb_en_60 (cislunar)  | 5.00 | 5 | 5 | 5 | 5 | ↑ +0.50 |
| drb_en_64 (UAV PID)   | 4.50 | 4 | 4 | 5 | 5 | ↓ -0.50 (was PERFECT) |
| drb_en_68 (K8s auto)  | 4.50 | 4 | 4 | 5 | 5 | = |
| drb_en_95 (Diamond)   | 5.00 | 5 | 5 | 5 | 5 | = |
| drb_en_100 (AI)       | 4.50 | 4 | 4 | 5 | 5 | ↑ +0.75 |

Judge rationale for the 3 weak cases (C=4, D=4):
- drb_en_64: "less detail on some methods' theoretical foundations; optimality metrics
  discussion is somewhat implicit." (Note: R6 was PERFECT — regression is likely variance.)
- drb_en_68: "not explicitly addressing existing projects as broadly as reference
  (PredictKube, Koordinator mentioned only briefly)."
- drb_en_100: "slightly less detailed than reference in some mechanistic explanations."

Pattern across all 3 weak cases: subagents find practical/overview content but miss:
(a) theoretical foundations / mathematical principles for named methods
(b) specific named tool comparisons or survey-level coverage

The current subagent prompt says "different keyword angles" without specifying what those
angles should be. Agents default to broad practical queries and miss academic/theoretical
search space.

## Candidate levers

1. **Structured search angles in subagent prompt** — explicitly tell subagents to cover
   three distinct search angles: (a) practical applications and named tools, (b) theoretical
   or academic foundations, (c) comparative surveys or benchmarks. This directly targets
   the "theoretical depth" gap (drb_en_64, drb_en_100) and "named tools" gap (drb_en_68).
   Hypothesis: DEPTH rises 4.40→4.80, COMP stays or rises. **← CHOSEN**

2. **More explicit synthesis depth in main agent** — tell main agent to include
   theoretical basis for each method. Risk: makes answers verbose or mismatches question
   style. Lower priority than getting the raw evidence via better searches.

3. **Force 3 searches per subagent** — more searches = more coverage. But Round 5
   showed forcing rigidity can backfire. Keep "2-3" for now.

## Choice + reason
Lever 1. The root cause is that subagents don't know to search the theoretical/academic
space. Adding explicit angle labels (practical → theoretical → comparative) costs nothing
extra in tokens and gives the model a clear search strategy.

Also combine with a light depth hint in main agent step 2: for each key method, include
its theoretical basis or mechanism, not just practical use.

## Specific changes

1. `_subagent_prompt` step 1: "Call `tavily_search` 2-3 times using DIFFERENT search
   angles, for example: (a) practical tools and implementations, (b) theoretical
   foundations or mathematical principles, (c) comparative studies or existing projects."

2. `_main_agent_prompt` step 2: append "For each key named method or technology,
   briefly explain its theoretical basis or mechanism of operation, not just its
   practical use."

## Success criteria
- RACE > 4.75 (beats 4.70 by >0.05 → "improved").
- DEPTH > 4.40.
- drb_en_64 recovers to RACE ≥ 4.50 (no further regression).
