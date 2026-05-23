# Round 1 — Establish baseline (no agent logic change)

## Current state
- HEAD: `0aa7291 initial project`
- `experiments/results.tsv` does not exist.
- Best RACE so far: N/A — this is the first measurement.

## Data analysis
No prior score data. This round's sole job is to record the starting point
so every future round can be judged against it.

The baseline agent uses:
- Main agent: temp 0.25, 2–4 subagent calls, ≥3000-word structured answer
- Subagent: temp 0.2, 2–5 Tavily searches, ≥1500-word findings
- Tavily: basic depth, 10 results per query
- No outline/planner, no self-critique, no refinement nodes

## Candidate levers for future rounds (deferred)
1. **Tighten subagent search cap** — replace the vague "2-5 times" cap with
   a hard per-call early-stop when sufficient entries are found; prevents
   gratuitous extra searches.
2. **Add an outline/planner node** — have the main agent decompose the
   question into named sub-topics before calling subagents; likely improves
   COMP and INST for multi-part questions.
3. **Boost Tavily to "advanced" depth** — richer snippets per result without
   more LLM calls; cost: higher Tavily $$ per query.
4. **Add self-critique / refinement pass** — main agent writes draft then a
   critic node lists gaps; main revises; likely raises DEPTH and COMP.
5. **Query diversification prompt** — instruct subagent to vary angle (year,
   region, mechanism, comparison) across its calls; targets COMP.

## Choice
No agent code change this round — pure baseline measurement.

## Success criteria
- All 5 cases complete and produce non-empty answers.
- `experiments/results.tsv` records a real RACE mean (> 0).
- Per-case judge rationales are saved to `judge.jsonl`; these will drive
  Round 2's lever selection.
