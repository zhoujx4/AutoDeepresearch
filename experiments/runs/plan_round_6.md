# Round 6 — Question decomposition before subagent dispatch

## Current state
- Best RACE: 4.35 (Round 4)
- Round 5 regressed to 4.05 (forcing "exactly 3" too rigid)
- Consistent pattern: COMP=3.80 across rounds 1,3,4 (never budges)

## Data analysis

The dataset has 7 explicit `must_cover` items per case, which the judge uses for COMP.
The agent never sees these items, but they are derivable from careful reading of the question.

Examples of ALWAYS-MISSED items:
- drb_en_68: "Strategies for Managing Non-Elastic Node Groups" — not in the obvious
  "predictive/scheduled autoscaling" search space; requires knowing K8s architecture
- drb_en_68: "Integration and Utilization of Business Request Volumes" — the question
  mentions it but agents search generically for "K8s autoscaling tools"
- drb_en_100: "Scope of Interpersonal Relationship Types Examined" — agents cover
  companions/colleagues but not family, romantic, etc.
- drb_en_100: "Consideration of Diverse User Populations and Sociocultural Contexts"

Root cause: subagents pick the most obvious queries and miss less-salient sub-topics
from the question. The main agent gives subagents broad scope rather than directing
them to cover specific named aspects.

## Candidate levers

1. **Question decomposition step before subagent dispatch** — instruct the main agent
   to first enumerate the key sub-topics required by the question (from reading it
   carefully), then assign each subagent to cover a specific subset. This ensures
   less-salient must-cover items get dedicated search attention.
   Hypothesis: COMP rises from 3.80 to 4.0+. **← CHOSEN**

2. **Pass a computed topic list to subagents** — as above, but via a LangGraph
   planner node. More complex; defer until prompt approach is tested.

3. **Re-try Round 4 config** — Round 4 was best (4.35) without forcing exact counts.
   The issue is that 4.35 is just barely above 4.30 and noise makes it fragile.
   Combining Round 4's "diversification" with Round 6's "decomposition" is the play.

## Choice + reason
Lever 1 (combined with Round 4's diversification approach). Keep "2-3 subagent calls"
(not rigid 3) and "2-3 searches", but add the question decomposition instruction.

## Specific change
In `_main_agent_prompt`, update step 1:
  "Before calling subagents, analyze the question and list its key sub-topics.
   Then dispatch each subagent to cover a specific group of 2-3 sub-topics,
   including less-obvious aspects like specific technology categories, edge cases,
   or practical constraints mentioned in the question."

## Success criteria
- RACE > 4.40 (beats 4.35 by >0.05 → "improved").
- COMP > 3.80.
