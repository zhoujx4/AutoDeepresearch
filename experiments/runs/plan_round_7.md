# Round 7 — Post-research coverage check before writing final answer

## Current state
- Best RACE: 4.55 (Round 6, status=improved)
- Dimension means R6: COMP=4.20, DEPTH=4.20, INST=4.80, READ=5.00

## Data analysis

Round 6 per-case:
| case | RACE | C | D | I | R | status |
|------|------|---|---|---|---|--------|
| drb_en_60 (cislunar) | 4.50 | 4 | 4 | 5 | 5 | good |
| drb_en_64 (UAV PID) | 5.00 | 5 | 5 | 5 | 5 | PERFECT |
| drb_en_68 (K8s auto) | 4.50 | 4 | 4 | 5 | 5 | recovered |
| drb_en_95 (Diamond)  | 5.00 | 5 | 5 | 5 | 5 | PERFECT |
| drb_en_100 (AI)      | 3.75 | 3 | 3 | 4 | 5 | ONLY WEAK CASE |

drb_en_100 is the sole remaining bottleneck. Its must_cover items include:
1. Breadth of AI Technologies ← covered sometimes
2. Scope of Interpersonal Relationship Types ← CONSISTENTLY MISSED
3. Changes in *How* Individuals Relate ← covered
4. Changes in *Why* Individuals Relate ← partially covered
5. Balanced Positive/Negative Impacts ← covered
6. Diverse User Populations & Sociocultural Contexts ← CONSISTENTLY MISSED
7. Long-Term Fundamental Changes ← partially covered

Items 2 and 6 keep getting missed. The question decomposition in Round 6 identified
them but still didn't consistently assign dedicated search coverage.

Pattern: after 2-3 subagent calls, the agent has evidence for 5/7 items and writes
the final answer without checking if items 2 and 6 have dedicated evidence.

## Candidate levers

1. **Post-research coverage check** — after subagent calls, instruct the main agent
   to list which identified sub-topics have evidence vs which are missing, and call
   one more subagent if a key sub-topic has no coverage. Lightweight self-critique.
   Hypothesis: drb_en_100 COMP rises 3→4 if one more targeted subagent call is made.
   Expected RACE delta: +0.15 to +0.25. **← CHOSEN**

2. **Hardcode 3 subagent calls always** — demonstrated instability in Round 5.
   Avoid.

3. **Topic-list extraction node** — separate LangGraph node that extracts sub-topics
   from the question before subagent dispatch. More complex. Defer.

## Choice + reason
Lever 1. The coverage-check step costs at most 1 extra subagent call per case
(when a sub-topic is missing), adds no overhead when coverage is complete, and
directly targets the observed failure mode (agent writes without checking gaps).

## Specific change
In `_main_agent_prompt`, add a step 1.5 between subagent calls and final answer:
  "After gathering research, quickly review which identified sub-topics now have
   evidence and which are still missing. If any important sub-topic lacks evidence,
   call research_subagent once more specifically for that topic before writing."

## Success criteria
- RACE > 4.60 (beats 4.55 by >0.05 → "improved").
- drb_en_100 RACE > 4.00.
- COMP > 4.20.
