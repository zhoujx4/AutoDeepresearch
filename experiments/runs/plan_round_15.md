# Round 15 — Add synthesis self-review step to catch depth gaps before finalizing

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11, 14)
- Persistent pattern: 3 cases perfect (64, 68, 95), 2 stuck at 4.5 (60, 100)

## Data analysis

Round 14 revealed:
- drb_en_60: D=5 (deep!) but R=4 (dense). C=4 (something missing). RACE=4.5.
- drb_en_100: C=4 (missing CPM theory, family/professional coverage). D=4. RACE=4.5.

The coverage check (step 1.5) successfully triggers extra research for MISSING topics.
But it doesn't help when a topic is PRESENT but covered superficially or at the wrong
level of depth. This is the current bottleneck: judge says "less emphasis on X" or
"slightly less detail on Y" — the topic is there, just not deep enough.

## Two-level quality assurance

Currently:
- Step 1.5: "Research coverage check" — if a sub-topic is MISSING, add a subagent call
- Step 2: Synthesis — write the final answer

Missing:
- "Synthesis depth check" — after writing, verify each sub-topic is covered at
  SUFFICIENT DEPTH, not just mentioned. Expand any superficial sections.

## Specific change

In `_main_agent_prompt` step 2:
Replace "Write the final answer as a single plain-text message." with:
"Draft your answer, then briefly review it against your step 1 sub-topic list:
for each sub-topic, verify it is covered in depth (not just mentioned). If any
sub-topic is addressed only superficially, expand that section. Then output the
final polished answer as a single plain-text message."

This is a within-synthesis metacognitive step — the agent does a quick internal
review and expands weak sections before finalizing. No extra LLM calls needed
(this happens within the single synthesis LLM call).

## Expected impact

- drb_en_100: Agent notices "family relationships" and "CPM/ethical framework" are
  mentioned briefly → expands them → COMP possibly 4→5
- drb_en_60: Agent notices "characterization/ID techniques" is dense → may reorganize
  to be clearer rather than just denser → R possibly 4→5
- Other cases: minimal impact (already well-covered, review confirms depth is ok)

## Risk

The self-review instruction adds processing within the synthesis step. The model might:
1. Just copy-paste rather than genuinely review — minimal harm
2. Over-expand every section → answers become too long → R drops
Mitigation: Keep "briefly review" phrasing to signal lightweight check.

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_100 RACE ≥ 4.75 (at least one dimension hits 5).
- drb_en_60 READ = 5.00 (density issue resolved).
