# Round 14 — Remove tool-list example from granularity instruction

## Current state
- Best RACE: 4.80 (Rounds 8, 10, 11)
- Round 13: RACE=4.75 (drb_en_60=5.0, drb_en_64=5.0 ← GREAT, drb_en_68=4.25 ← REGRESSION)

## Root cause of Round 13 regression

Round 13's granularity instruction included TWO examples:
1. "for control methods list 'MRAC', 'ADRC', 'H-infinity'" → HELPFUL for drb_en_64
2. "for scaling tools list 'Karpenter', 'KEDA' specifically" → HARMFUL for drb_en_68

The tool example caused the K8s agent to identify ALL specific autoscaling tools as
sub-topics (PHPA, KEDA, Karpenter, CAST AI, CronHPA, etc.) and try to cover each at
depth. This made the answer "dense" → READ dropped from 5 to 4 → RACE=4.25.

Meanwhile, the method example helped drb_en_64 find MRAC and ADRC (now mentioned in
the rationale) → drb_en_64=5.0 (PERFECT).

## Fix

Remove the tool-list example ("for scaling tools list 'Karpenter', 'KEDA' specifically")
from the granularity instruction. Keep only the method-level example (MRAC, ADRC,
H-infinity). This preserves the benefit for control/algorithm questions without
causing tool-enumeration density for K8s-style questions.

## Expected outcome

Without the tool-list example, the K8s agent will NOT try to enumerate all tools at
equal depth. It will cover tools at their natural level of prominence (most important
in depth, others briefly). READ should return to 5.

With method-level granularity still instructed, drb_en_64's MRAC/ADRC coverage
should be maintained.

If drb_en_60=5.0 + drb_en_64=5.0 + drb_en_68=5.0 + drb_en_100=4.5:
RACE = (5+5+5+5+4.5)/5 = 4.90 > 4.85 ✓ (improved)

## Specific change

`_main_agent_prompt` step 1: Remove "(e.g., ... for scaling tools list 'Karpenter',
'KEDA' specifically)" — keep only the control-methods example.

New text: "Go down to specific named methods, algorithms, or techniques — not just
broad categories (e.g., for control methods list 'MRAC', 'ADRC', 'H-infinity' rather
than 'advanced control')."

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- drb_en_68 READ = 5.00 (no density regression).
- drb_en_64 RACE = 5.00 (method coverage preserved).
