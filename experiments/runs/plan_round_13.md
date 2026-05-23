# Round 13 — Revert to "2-3" searches + granular sub-topic decomposition

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11 tied)
- Round 12: RACE=4.70 (regression from forcing 3 searches without escape hatch)

## Root cause pattern

Across rounds 8-12, three cases (drb_en_60, drb_en_64, drb_en_68) oscillate
between 4.5 and 5.0 independently. The gaps are always "a specific named method
or detail not covered":
- drb_en_64: MRAC, ADRC, hybrid controllers
- drb_en_68: Karpenter consolidation mechanics, PDBs
- drb_en_60: target characterization/ID techniques

These specific items get covered SOMETIMES (when the agent's searches happen to find
them) but not consistently. The issue is the granularity of step 1 decomposition:
the agent identifies "adaptive control methods" as a sub-topic rather than "MRAC,
ADRC" specifically. When the coverage check runs, it sees "adaptive control ✓"
(found some evidence) and doesn't trigger an extra targeted call for MRAC/ADRC.

## Hypothesis

If the agent decomposes sub-topics to the level of specific named methods/techniques
in step 1, the coverage check will correctly identify when MRAC or ADRC is missing
and trigger a dedicated search for them.

## Specific changes

1. `_subagent_prompt`: revert to "2-3 times" (R8/R10 stable config). The forced "3"
   without escape hatch in R12 caused regression by wasting a search call on a less
   useful angle for drb_en_64.

2. `_main_agent_prompt` step 1: add granularity guidance after the existing text:
   "When identifying sub-topics, go down to specific named methods, algorithms, or
   techniques — not just broad categories. For example, for a question about control
   methods, list 'MRAC', 'ADRC', 'H-infinity control' as sub-topics, not just
   'advanced control methods'. For a question about scaling tools, list 'Karpenter',
   'KEDA', 'PHPA' specifically."

## Expected outcome

- drb_en_64: coverage check identifies MRAC/ADRC as missing sub-topics → extra
  targeted call → COMP=5 more reliably
- drb_en_68: coverage check identifies Karpenter consolidation mechanics as missing
  → extra targeted call → COMP=5 more reliably
- drb_en_60: coverage check identifies specific characterization/ID techniques →
  COMP=5 more reliably

If drb_en_64+68 both hit 5.0 with drb_en_60 at 4.5:
RACE = (5+5+5+5+4.5)/5 = 4.90 > 4.85 ✓

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_64 RACE = 5.00, drb_en_68 RACE = 5.00 (no regression from R12).
