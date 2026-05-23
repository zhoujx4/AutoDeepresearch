# Round 9 — Expand coverage check to catch temporal and motivational dimension gaps

## Current state
- Best RACE: 4.80 (Round 8, status=improved)
- Dimension means R8: COMP=4.60, DEPTH=4.60, INST=5.00, READ=5.00

## Data analysis

Round 8 per-case:
| case | RACE | C | D | I | R | vs R7 |
|------|------|---|---|---|---|-------|
| drb_en_60 (cislunar)  | 4.50 | 4 | 4 | 5 | 5 | ↓ -0.50 (was PERFECT R7) |
| drb_en_64 (UAV PID)   | 5.00 | 5 | 5 | 5 | 5 | ↑ +0.50 (recovered) |
| drb_en_68 (K8s auto)  | 5.00 | 5 | 5 | 5 | 5 | ↑ +0.50 (NEW PERFECT) |
| drb_en_95 (Diamond)   | 5.00 | 5 | 5 | 5 | 5 | = |
| drb_en_100 (AI)       | 4.50 | 4 | 4 | 5 | 5 | = |

3 cases now perfect. 2 remaining weak cases:

**drb_en_60 (cislunar)**: Oscillates 4.5↔5.0 across rounds. The judge rationale in R8
praises the answer extensively but still gives C=4, D=4. No specific gap named — suggests
the answer is close to the threshold. Likely LLM variance; hard to fix via prompting.

**drb_en_100 (AI social)**: Consistent 4.5. Judge explicitly names the remaining gaps:
- "Less emphasis on long-term fundamental change compared to the reference"
- "Explicit discussion of 'why' shifts in motivation could be expanded"

These match exactly the must_cover items that have been partially covered since Round 7:
- Item 4: Changes in *Why* Individuals Relate — "expanded"
- Item 7: Long-Term Fundamental Changes — "less emphasis"

The current coverage check (step 1.5) watches for missing sub-topics but doesn't
explicitly flag temporal-scope gaps (near-term vs long-term) or motivational-scope
gaps (how vs why). After 2-3 subagent calls, the agent has most content but these
two cross-cutting dimensions get insufficient dedicated coverage.

## Candidate levers

1. **Expand coverage check to include analytical dimension verification** — beyond
   sub-topic checklist, explicitly verify: (a) long-term/future implications addressed,
   (b) 'why' motivations covered (not just 'how' mechanisms), (c) diverse populations
   addressed. These are the two specific gaps for drb_en_100 and general enough to
   improve other cases without harm.
   Hypothesis: drb_en_100 RACE 4.50→5.00. **← CHOSEN**

2. **Add dedicated long-term search angle to subagent** — add "(d) long-term trends
   and future projections" to subagent search angles. This would directly surface
   long-term change evidence. Could combine with Lever 1.

3. **Longer synthesis** — instruct main agent to be more thorough. Risk: verbose
   answers that hurt READ or INST.

## Choice + reason
Lever 1 + a light addition of Lever 2 (add long-term angle to subagent search examples).

The analytical dimension check in step 1.5 directly targets the two named gaps in
drb_en_100. The long-term angle in subagent ensures evidence is fetched, while the
expanded coverage check ensures the agent writes about it.

## Specific changes

1. `_main_agent_prompt` step 1.5: expand coverage check to verify not just sub-topics
   but also temporal (long-term) and motivational (why) dimensions:
   "After gathering research, review your identified sub-topics and verify:
   (a) each sub-topic has evidence, (b) long-term/future implications are addressed
   where relevant, (c) 'why' motivations are covered alongside 'how' mechanisms.
   If any gap exists, call research_subagent once more targeting that gap."

2. `_subagent_prompt` step 1: add "(d) long-term trends or future implications"
   to the search angle examples.

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_100 RACE = 5.00.
