# Round 16 — Revert R14+R15 regressions, add readability formatting hint

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11, 14)
- Round 15: RACE=4.45 (SEVERE regression: drb_en_60 I=2!)
- drb_en_60 got I=2 because the self-review step caused the agent to produce a
  malformed answer (draft + review commentary instead of clean final text)

## Root cause of Round 15 regression

The self-review instruction: "Draft your answer, then briefly review it against your
sub-topic list... expand before finalizing" caused the agent to output a literal
draft + review + expansion sequence rather than a clean final answer. The judge
penalized it as failing to follow task instructions (I=2).

Additionally, the granularity instruction (R13/R14) proved unstable:
- Helps drb_en_64 find MRAC/ADRC
- Causes density in drb_en_60 (R=4) or drb_en_68 (R=4) alternately
- The swing is unpredictable

## Strategy

Revert to EXACTLY Round 10's configuration (the most stable 4.80 base). Then add
ONE minimal change targeting the persistent density issue for drb_en_60.

R10 configuration was:
- Step 1: question decomposition (no granularity instruction)  
- Step 1.5: basic coverage check
- Step 2: synthesis depth + sociocultural hints
- Subagent: "2-3 times" + structured angles (a,b,c)

This consistently gives: drb_en_64=5.0, drb_en_68=5.0, drb_en_95=5.0, 
drb_en_100=4.5, drb_en_60=4.5 (density) → RACE=4.80.

New addition: formatting hint in step 2 to prevent density while helping typology:
"When covering many specific methods or tools, use clear tables and structured lists
rather than dense prose."

This helps two cases:
1. drb_en_60: dense math → would use tables → R might improve to 5
2. drb_en_100: needs a typology table (cited in several judge rationales) → might
   now include one → COMP might improve

## Specific changes

1. Remove granularity instruction from step 1 (back to R10)
2. Remove self-review step from step 2 (back to R10's simple "Write the final answer")
3. Add one sentence at end of step 2: "When covering many specific methods or tools,
   use clear tables and structured lists rather than dense prose to maintain readability."

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_60 READ = 5.00 (no density).
- drb_en_100 COMP = 5.00 (typology table triggers from formatting hint).
