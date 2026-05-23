# Round 12 — Remove escape hatch so subagent reliably makes 3 searches

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11 all tied)
- Agent tokens R10=262K (73 calls), R11=229K (59 calls)

## Root cause of Round 11 failure

R11 changed the subagent instruction to "Call `tavily_search` 3 times... (you may use
only 2 if the topic is very narrow and 2 clearly cover it fully)."

The escape hatch was too permissive: the model interpreted "very narrow" broadly and
defaulted to 2 searches in almost every case. R11 actually has FEWER total calls (59)
and FEWER agent tokens (229K) than R10 (73 calls, 262K tokens). The instruction
nominally increased the default but actually decreased coverage.

Result: drb_en_68 regressed from 5.0 (R10) to 4.5 (R11) because fewer searches
missed "Prophet formula and Karpenter consolidation details." drb_en_60 improved
(5.0) likely due to stochastic variation, not the instruction change.

## Fix

Remove the escape hatch. Firm default of 3 searches without a "may use 2" clause.

This is different from Round 5's "exactly 3 searches each" regression:
- R5 forced BOTH main agent (3 subagent calls) AND subagent (3 searches) = 9 total,
  causing third subagent call to be low-quality
- R12 only changes SUBAGENT search count; main agent stays at "2-3 subagent calls"
  (typically 2). Net total: 2 subagents × 3 searches = 6 searches (vs R10's ~4-6)

## Expected outcome

More evidence per subagent call → better chance of finding specific implementation
details (Prophet formula, Karpenter consolidation, cislunar characterization) →
drb_en_68 and drb_en_60 more reliably at 5.0.

If drb_en_60 + drb_en_68 both hit 5.0 with drb_en_100 at 4.5:
RACE = (5+5+5+5+4.5)/5 = 4.90 > 4.85 ✓ (improved)

## Specific change

`_subagent_prompt`: "Call `tavily_search` 3 times using DIFFERENT search angles..."
— remove the "(You may use only 2...)" line entirely.

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_68 RACE = 5.00 (no regression).
- drb_en_60 RACE ≥ 4.50.
