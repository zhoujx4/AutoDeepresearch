# Round 10 — Revert R9 regression, add targeted sociocultural synthesis hint

## Current state
- Best RACE: 4.80 (Round 8, status=improved)
- Round 9: RACE=4.50 (regression, status=recorded)
- Dimension means R8: COMP=4.60, DEPTH=4.60, INST=5.00, READ=5.00

## Root cause analysis of Round 9 regression

Round 9 made two changes:
1. Added "(d) long-term trends or future implications" to subagent search angles
2. Added "(b) long-term implications addressed" and "(c) why motivations covered" 
   to the coverage check (step 1.5)

Both changes were harmful for technical cases:
- drb_en_60 (cislunar): C=4,D=4 → C=3,D=3 (crashed to 3.5)
  Cause: extra subagent calls triggered by "(b) long-term implications" check
  fetched cislunar future-policy content instead of specific tracking algorithms.
  Also, "(d) long-term trends" angle caused subagents to waste a search call on
  irrelevant futuristic content.
- drb_en_68 (K8s): RACE 5.0 → 4.5 (similar regression)

drb_en_100 did benefit: judge confirmed ALL 7 must_cover items covered (including
long-term changes). But COMP=4 persists: "slightly less exhaustive coverage of
sociocultural contexts compared to the reference."

So the residual gap for drb_en_100 is COMP quality, not coverage presence:
sociocultural contexts are mentioned but not as exhaustively as the reference.

## Strategy

Revert R9's two changes (harmful to technical cases), then add a single minimal
instruction to the synthesis step that only activates for social/behavioral questions.

## Specific changes

1. Revert `_subagent_prompt`: remove "(d) long-term trends" → back to R8 (a,b,c only)
2. Revert step 1.5: remove "(b) long-term implications" and "(c) why motivations" →
   back to R8's simple sub-topic coverage check
3. Add to `_main_agent_prompt` step 2 synthesis: "For questions about social,
   behavioral, or cultural impacts, include specific examples from diverse cultural
   and demographic contexts—not just general statements."

Change 3 is synthesis-only (doesn't affect search) and conditional on question type,
so it won't trigger for cislunar/K8s questions.

## Expected outcome

- drb_en_60: returns to R8 level (4.5 — sub-topic coverage check no longer triggers
  spurious long-term extra calls)
- drb_en_68: returns to R8 level (5.0)
- drb_en_100: COMP gap closes from "sociocultural contexts slightly under-covered" →
  "fully covered with diverse examples". COMP 4 → 5.
  RACE 4.5 → 5.0.
- Overall RACE: (5+5+5+5+4.5)/5 = 4.90

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_100 RACE ≥ 5.00.
- drb_en_60 RACE ≥ 4.50 (no further regression).
