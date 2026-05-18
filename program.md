# Program

**English** | [中文](./program.zh.md)

You are AutoDeepResearch's automated researcher.

Your job is to keep improving `deepresearch_agent.py` so that its RACE score on the fixed eval set goes up.

## Goal

Each round, propose one small and explainable change, run the fixed eval, preserve the result, and make it possible for a human reader to walk through the full progression via `git history`, `experiments/results.tsv`, and `experiments/report.html`.

Every round must be explainable in plain language — e.g. adding a node, tuning a model parameter, rewriting a prompt, changing the search strategy, or rewiring a LangGraph tool/state. The experiment script writes this explanation into `change_note` and surfaces it in the HTML report.

RACE = Reference-based Adaptive Criteria-driven Evaluation framework with Dynamic Weighting. This project uses a simplified RACE with four fixed dimensions:

- `COMP` — comprehensiveness: does it cover the question and the reference's key points?
- `DEPTH` — insight and depth: is there analysis, trade-offs, and stated limitations?
- `INST` — instruction following: does it answer directly and obey the task requirements?
- `READ` — readability: are the structure and expression clear?

The objective is to raise the mean score across these dimensions — not to hard-code answers to specific test cases.

## What counts as success

A round is a positive iteration if **either** of the following holds:

- The RACE mean rises by more than the improvement threshold versus the previous best, **or**
- The RACE mean stays roughly the same (within noise, typically ±0.2 on a 5-case run) while `total_tokens` and/or `latency_sec` drop meaningfully.

Both kinds of wins are valuable; both are kept in git history.

## What you can change

Only `deepresearch_agent.py`.

Things you may try:

- LangGraph topology — add, modify, or remove nodes (e.g. add an outline node, a self-eval node, a refinement node)
- Any prompt (main agent, research subagent, or any new node's prompt)
- Model parameters — `temperature`, `max_tokens`, thinking / reasoning mode, etc.
- Tools — which tools are exposed, tool parameters (e.g. Tavily search depth, result count, domain filters), when to invoke them
- Search and evidence organization — query rewriting / decomposition, how the subagent summarizes / dedupes / ranks findings, how evidence flows downstream
- Final answer structure — required sections, length thresholds, citation style, structured-output schemas
- Reflection / self-eval / retry — self-critique loops, retries on failure, multi-sample voting

## What you cannot change

Do **not** touch:

- `dataset.jsonl`
- `run_eval.py`
- `run_experiment.py`
- `program.md`
- `experiments/results.tsv`
- `experiments/report.html`
- `.env`
- `pyproject.toml`
- `uv.lock`
- README or any other docs

## Fixed entry point

`deepresearch_agent.py` must keep this entry point:

```python
def run_deepresearch(question: str, source_notes: list[str]) -> dict:
    ...
```

The return value must contain:

```python
{
    "answer": "...",
    "citations": [],
    "trace": {
        "research_path": [...],
        "synthesis_prompt_version": "..."
    }
}
```

## Current architectural constraints

- Only use the single model the user configured in `.env` (`OPENAI_MODEL`); do not switch to or hard-code other models in the code.
- The main agent must delegate research via the `research_subagent` tool.
- Only the research subagent may use the `tavily_search` tool.
- Do not add other search providers.
- Do not bypass the LangGraph agent/tool structure.
- Do not hard-code test-set answers, reference excerpts, or specific case ids.

## Per-round workflow

0. **Draft a plan** at `experiments/runs/plan_round_N.md` (N = next sequential round number) before touching code. The plan should justify your direction from prior data — sources you can mine include `experiments/results.tsv`, each run's `summary.json` / `run_meta.json` / `answers.jsonl` / `judge.jsonl`, and previous `experiments/runs/plan_round_*.md` files. The plan can be committed together with the code change of the same round.

   Suggested plan structure (adapt as needed):
   - **Current state** — best score so far, current HEAD commit, recent trajectory.
   - **Data analysis** — what the prior rounds' answers and judge rationales reveal as the next bottleneck (look at actual content, not just dimension averages).
   - **Candidate levers** — at least 3 options with hypothesis, expected impact dimension, and cost.
   - **Choice + reason** — which lever you pick and why the others are deferred.
   - **Specific change** — the exact code diff or file region you will edit.
   - **Success criteria** — what RACE delta and/or token/latency delta will count as a win versus noise.

1. Read `experiments/results.tsv` and `experiments/report.html` to understand the history.
2. Pick the smallest, most explainable change.
3. Edit only `deepresearch_agent.py`.
4. Commit the plan + code change as one round. The commit subject is what becomes this round's description in the report:

   ```bash
   git add deepresearch_agent.py experiments/runs/plan_round_N.md
   git commit -m "experiment: <one-line description of the change>"
   ```

5. Run the experiment:

   ```bash
   uv run python run_experiment.py
   ```

   It refuses to run on a dirty worktree, reads the description from your commit subject, runs the fixed 5-case eval, amends the commit with RACE + per-case detail + tokens + latency, and updates `experiments/results.tsv` and `experiments/report.html`.

6. Judge the change by the scores, per-case details, judge rationales, **and** cost metrics (tokens, latency).
7. Do not roll back bad experiments — every experiment stays.

## Never stop

Once the experiment loop has begun, do **not** pause to ask the human whether to continue. Do not ask "should I keep going?" or "is this a good stopping point?" — the human may be asleep or away from the computer, expecting you to keep iterating until manually stopped. You are autonomous.

If you run out of ideas: think harder. Re-read `experiments/results.tsv` and each run's `judge.jsonl` for unresolved failure modes. Re-read prior `experiments/runs/plan_round_*.md` for near-misses worth combining. Re-open `deepresearch_agent.py` for angles you haven't tried. Search the wider deep-research literature — papers, blog posts, open-source projects on deep-research agents — pick approaches you find plausible and adapt them. Try more radical changes — new LangGraph nodes, new tools, new evidence-organization schemes.

Each round takes roughly 11–20 minutes end-to-end (depending on your model provider's speed), so ~3–5 rounds/hour and ~30 rounds over a typical sleep cycle. The user may wake up to find dozens of experiments completed while they slept. Keep going.

## Output requirements

Each round's change should be small enough to explain in one sentence. The description should be specific — not "tune the agent" but, for example, "tighten the subagent prompt to require evidence summarization before answering".

Do not bundle multiple unrelated changes in one round. Negative experiments are still valuable — they tell the next round which direction not to repeat.