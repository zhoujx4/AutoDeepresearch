# Round 17 — Pure revert to R10 configuration (proven 4.80 base)

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11, 14)
- Round 16: RACE=4.70 (drb_en_100 crashed to 4.0 due to formatting hint)

## Root cause analysis

Every modification since R10 has either:
1. Caused a swap (60 improves, 68 regresses or vice versa) → net zero
2. Caused a crash in drb_en_100 → regression
3. Introduced instability without improvement

R10 → R11: 3-search default with escape hatch → 60 improved, 68 regressed → net 4.80
R10 → R12: forced 3 searches → 64 regressed → net 4.70
R10 → R13: granularity instruction → 60, 64 improved but 68 crashed (READ=4) → net 4.75
R10 → R14: removed tool example → 68 recovered but 60 density issue → net 4.80
R10 → R15: self-review step → drb_en_60 I=2 → net 4.45 (severe regression)
R10 → R16: formatting hint → drb_en_100 crashed (C=3) → net 4.70

Pattern: Any change that helps one case hurts another. The R10 configuration is
the Nash equilibrium — changing anything makes things worse on average.

## Decision

Pure revert to EXACTLY Round 10's configuration. No additions.

R10 configuration:
- Step 1: broad sub-topic identification (no granularity instruction)
- Step 1.5: basic coverage check ("if any important sub-topic still lacks evidence")
- Step 2: synthesis depth + sociocultural hints only
- Subagent: "2-3 times" + structured search angles (a,b,c)

This gives the expected result: drb_en_64=5.0, drb_en_68=5.0, drb_en_95=5.0 
reliably, with drb_en_60=4.5 and drb_en_100=4.5 → RACE=4.80.

## After establishing R10 baseline again

If R17 confirms RACE=4.80, Round 18 will try a more fundamental approach:
- Expanding the coverage check trigger condition: "lacks evidence OR is only 
  superficially covered (insufficient specific detail)" — to catch the "covered 
  but shallow" case that plagues drb_en_100

This is different from the self-review step (which operated at synthesis time and
caused confusion). A research-time sensitive trigger would call another subagent
BEFORE synthesis for shallow topics.

## Specific change

Remove the formatting hint from step 2:
"When covering many specific methods or tools, use clear tables and structured lists
rather than dense prose to maintain readability."

Everything else stays as R10.

## Success criteria
- RACE = 4.80 (confirming R10 baseline recovery).
- drb_en_100 RACE ≥ 4.50 (no crash from formatting).
- drb_en_68 RACE = 5.00 (reliable).
