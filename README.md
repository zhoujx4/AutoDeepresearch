# AutoDeepResearch

**English** | [中文](./README.zh.md)

A minimal deep research agent that self-improves through iterative experiments, inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

The goal: let an LLM act as an automated researcher, repeatedly modifying a small deep research agent, running a fixed evaluation, and recording every round — good experiments and bad ones are both kept.

**[Live experiment report](https://zhoujx4.github.io/AutoDeepresearch/experiments/report.html)** — RACE scores, per-case judge rationales, and code diffs for every round.

## Core idea

- Mutable code lives in `deepresearch_agent.py`.
- The eval set is fixed at `dataset.jsonl`.
- The eval logic is fixed at `run_eval.py`.
- Each round makes one small change.
- All experiments are preserved as git commits + result records; bad experiments are not rolled back.
- `experiments/report.html` is the human-readable view; `experiments/results.tsv` is the machine-readable history.
- Each round emits a natural-language change note stored in `change_note` and surfaced in the HTML report.

## Agent architecture

The agent is built on LangGraph / LangChain:

- A **main agent** decomposes the question and writes the final answer.
- The main agent can only delegate research via the `research_subagent` tool.
- The **research subagent** calls the `tavily_search` tool to query the web.
- Search results are cited with markers like `[S1]`, `[S2]` that are globally unique across all subagent calls.

## Evaluation

**Test set**: 5 tasks randomly sampled from [DeepResearch Bench](https://github.com/Ayanami0730/deep_research_bench)'s 100 official research tasks (RACE paper: [arXiv:2506.11763](https://arxiv.org/abs/2506.11763)), pinned in `dataset.jsonl`. Each entry carries the original question, the official reference report, and `must_cover` checkpoints extracted from the benchmark's comprehensiveness criteria.

**Scoring**: a simplified RACE (Reference-based Adaptive Criteria-driven Evaluation framework with Dynamic Weighting), four fixed dimensions, each scored 1–5:

- `COMP` — comprehensiveness: does it cover the question and reference points?
- `DEPTH` — insight and depth: is there analysis, trade-offs, and stated limitations?
- `INST` — instruction following: does it answer directly and obey the task requirements?
- `READ` — readability: are the structure and expression clear?

An LLM judge (`OPENAI_JUDGE_MODEL`) returns scores + a short rationale as JSON. The RACE score is the mean of the four dimensions.

**Cost metrics**: every round also records `latency_sec`, `agent_tokens`, `judge_tokens`, `total_tokens`, and `agent_llm_calls`. Reducing tokens or latency at the same RACE score also counts as a successful iteration.

## Repository layout

```text
deepresearch_agent.py            Agent code the auto-experimenter improves
program.md                       Instruction manual for the auto-experimenter
run_eval.py                      Fixed RACE evaluator
run_experiment.py                Orchestrates one experiment round
dataset.jsonl                    Fixed eval set
experiments/results.tsv          Machine-readable history
experiments/report.html          Human-readable report
experiments/runs/plan_round_*.md Per-round iteration plan (committed to git)
.env                             Local environment variables (not committed)
.env.example                     Environment template
```

## Quick start

```bash
cd AutoDeepResearch
uv sync
```

Copy `.env.example` to `.env` and fill in your model + search keys:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
TAVILY_API_KEY=...
```

Run a smoke test (one case):

```bash
uv run python run_eval.py --limit 1
```

Run the full 5-case eval:

```bash
uv run python run_eval.py --limit 5
```

Run one full experiment round (runs the eval against your latest commit, amends that commit with the score, updates the TSV and HTML report):

```bash
git add deepresearch_agent.py experiments/runs/plan_round_N.md
git commit -m "experiment: <one-line description of the change>"
uv run python run_experiment.py
```

The auto-experimenter (the current interactive AI session, or you) writes the plan, edits `deepresearch_agent.py`, commits, then runs `run_experiment.py`. The script reads the commit subject as the round's description and refuses to run if the working tree has uncommitted changes.

## Experiment loop

Each round looks like this:

```text
read prior results + per-case answers/rationales
  -> draft experiments/runs/plan_round_N.md
       (state diagnosis, candidate levers, choice + reason, success criteria)
  -> edit deepresearch_agent.py
  -> git commit -m "experiment: <description>"
  -> run run_experiment.py
       -> read description from HEAD commit subject
       -> run 5 cases in parallel
       -> RACE judge scores each
       -> amend the commit with RACE + per-case detail + tokens + latency
       -> append to results.tsv and rewrite report.html
  -> next round
```

`run_experiment.py` never rolls back on a score drop. A round whose RACE rises above the previous best by more than the improvement threshold is tagged `improved`; everything else that completed cleanly is `recorded`.

## Reading the results

- Open `experiments/report.html` for per-round change notes, code diffs, case scores, candidate answers, and judge rationales.
- Inspect `experiments/results.tsv` for trend analysis. Columns: `commit, race_score, COMP, DEPTH, INST, READ, latency_sec, agent_tokens, judge_tokens, total_tokens, agent_llm_calls, status, description, change_note`.
- `git log --oneline` shows each round's RACE score in the commit subject; `git show <commit>` reveals the full commit body with per-case details.
- `experiments/runs/plan_round_*.md` traces the decision behind each round.
