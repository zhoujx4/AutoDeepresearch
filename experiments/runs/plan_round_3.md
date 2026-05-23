# Round 3 — More search coverage + soft depth hint; no rigid format

## Current state
- Best RACE: 4.20 (Round 1 baseline) — Round 2 went down to 3.80 (recorded)
- Dimension means at baseline: COMP=3.80, DEPTH=3.80, INST=4.60, READ=4.60

## Data analysis (Round 1 vs Round 2)

Per-case comparison:
| case | R1 RACE | R2 RACE | INST Δ | key R2 judge note |
|------|---------|---------|--------|-------------------|
| drb_en_60 | 4.50 | 3.25 | 5→2 | format overrode question's expected structure |
| drb_en_64 | 4.50 | 4.50 | 5→5 | stable |
| drb_en_68 | 3.50 | 3.75 | 4→4 | small DEPTH gain |
| drb_en_95 | 5.00 | 4.25 | 5→5 | READ dropped 5→4 |
| drb_en_100| 3.50 | 3.25 | 4→2 | format overrode "write a paper" requirement |

Root causes:
1. The Findings/Analysis/Limitations format imposed a specific section structure that
   conflicts with question-specific formats (cislunar SSA guide, academic paper). This
   directly tanks INST for those questions.
2. COMP stayed at 3.0 for the two weak cases despite the format addition — COMP is
   driven by *what* topics are covered, not by structural sections.
3. DEPTH did improve (3→4 for drb_en_68, drb_en_100) — the depth nudge concept
   works, but as a *soft* hint, not a rigid format override.

Primary bottleneck: COMP=3.80 (missing sub-topics in drb_en_68 and drb_en_100).
Secondary: DEPTH=3.80 (insufficient analysis depth).

## Candidate levers

1. **Soft depth hint + more search calls** — Remove the rigid output format; add one
   sentence "Include analysis of trade-offs, limitations, and open questions." Increase
   subagent calls from "once or twice" to 2-3. Increase search calls from 1-2 to 2-3.
   Hypothesis: COMP↑ (more topics covered), DEPTH↑ slightly (soft nudge),
   INST recovers (no format override). **← CHOSEN**

2. **Outline/planner node before subagent dispatch** — Decompose question into named
   sub-topics first. Targets COMP directly. Cost: +1 LLM call + more complexity.
   Deferred — try cheaper lever first.

3. **Pass must-cover list from the question to main agent explicitly** — The dataset
   has `must_cover` items in dataset.jsonl. If the main agent is told what must be
   covered, it can direct subagents more precisely. Cost: requires threading
   source_notes differently. Deferred.

## Choice + reason
Lever 1. Addresses the COMP bottleneck (more searches = more sub-topic coverage)
and repairs the INST damage from Round 2 (no rigid format). Cost is modest: +30%
more search calls, +50% more subagent calls.

## Specific changes
In `deepresearch_agent.py`:
- `_main_agent_prompt`: replace rigid Findings/Analysis/Limitations block with one
  soft sentence about depth. Change "once or twice" → "2-3 times".
- `_subagent_prompt`: change "1-2 times" → "2-3 times".

## Success criteria
- RACE mean > 4.25 (beats baseline by >0.05).
- COMP mean > 3.80 (primary target).
- INST mean ≥ 4.40 (recovers from Round 2 damage — not lower than baseline).
