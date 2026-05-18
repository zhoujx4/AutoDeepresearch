from __future__ import annotations

import html
import json
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from run_eval import run_eval


RESULTS_TSV = ROOT / "experiments" / "results.tsv"
REPORT_HTML = ROOT / "experiments" / "report.html"
IMPROVEMENT_THRESHOLD = 0.05


def main() -> int:
    _ensure_git_repo()
    _require_clean_worktree()
    best_score = _read_best_score()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "experiments" / "runs" / run_id

    commit = _git(["rev-parse", "HEAD"]).strip()
    description = _read_head_description()
    diff_summary = _git(["show", "--stat", "--oneline", "--no-renames", "--format=short", commit], check=False).strip()
    change_note = _build_change_note(commit, description)

    status = "crash"
    score = 0.0
    dimension_means: dict = {}
    summary_obj: dict = {}
    started = time.time()

    try:
        summary_obj = _run_eval(out_dir)
        score = float(summary_obj["race_score_mean"])
        dimension_means = summary_obj.get("dimension_means", {})
        status = "improved" if score > best_score + IMPROVEMENT_THRESHOLD else "recorded"
    except Exception as exc:
        description = f"{description}; error={exc}"
        status = "crash"

    latency = round(time.time() - started, 3)
    _append_result(commit, score, dimension_means, latency, status, description, change_note, summary_obj)
    _write_run_meta(out_dir, run_id, commit, score, dimension_means, latency, status, description, change_note, diff_summary, summary_obj)
    _write_html_report()

    # Fold all eval outputs into the experiment commit so each round is one
    # self-contained snapshot: code + plan + answers + judge + summary + run_meta
    # + updated results.tsv + regenerated report.html.
    _git([
        "add",
        str(out_dir.relative_to(ROOT)),
        "experiments/results.tsv",
        "experiments/report.html",
    ])
    if status == "crash":
        _git(["commit", "--amend", "--no-edit"], check=False)
    else:
        amended_message = _build_commit_message(description, score, dimension_means, summary_obj, out_dir)
        _git(["commit", "--amend", "-m", amended_message])
    commit = _git(["rev-parse", "HEAD"]).strip()

    print(json.dumps({"commit": commit, "race_score": score, "status": status}, ensure_ascii=False, indent=2))
    return 0 if status != "crash" else 1


def _require_clean_worktree() -> None:
    dirty = _git(["status", "--porcelain"], check=False).strip()
    if dirty:
        raise SystemExit(
            "Working tree has uncommitted changes. Commit your experiment first:\n"
            "  git add deepresearch_agent.py experiments/runs/plan_round_N.md\n"
            "  git commit -m 'experiment: <one-line description>'\n"
            "Then re-run: uv run python run_experiment.py"
        )


def _read_head_description() -> str:
    subject = _git(["log", "-1", "--format=%s"], check=False).strip()
    prefix = "experiment: "
    if subject.startswith(prefix):
        return subject[len(prefix):]
    return subject


def _run_eval(out_dir: Path) -> dict:
    return run_eval(ROOT / "dataset.jsonl", 5, out_dir)


def _ensure_git_repo() -> None:
    if not (ROOT / ".git").exists():
        _git(["init"])
        _git(["add", "."])
        _git(["commit", "-m", "initial project"], check=False)


def _read_best_score() -> float:
    if not RESULTS_TSV.exists():
        return 0.0
    best = 0.0
    lines = RESULTS_TSV.read_text(encoding="utf-8").splitlines()
    if not lines:
        return best
    header = lines[0].split("\t")
    score_index = header.index("race_score") if "race_score" in header else 1
    status_index = header.index("status") if "status" in header else 4
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) > max(score_index, status_index) and parts[status_index] in {"keep", "improved", "recorded"}:
            best = max(best, float(parts[score_index]))
    return best


def _append_result(
    commit: str,
    score: float,
    dimension_means: dict,
    latency: float,
    status: str,
    description: str,
    change_note: str,
    summary: dict | None = None,
) -> None:
    RESULTS_TSV.parent.mkdir(parents=True, exist_ok=True)
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(
            "commit\trace_score\tCOMP\tDEPTH\tINST\tREAD\tlatency_sec\tagent_tokens\tjudge_tokens\ttotal_tokens\tagent_llm_calls\tstatus\tdescription\tchange_note\n",
            encoding="utf-8",
        )
    summary = summary or {}
    agent_tokens = int(summary.get("agent_tokens_total", 0))
    judge_tokens = int(summary.get("judge_tokens_total", 0))
    total_tokens = int(summary.get("tokens_total", agent_tokens + judge_tokens))
    agent_calls = int(summary.get("agent_llm_calls_total", 0))
    with RESULTS_TSV.open("a", encoding="utf-8") as file:
        safe_description = description.replace("\t", " ").replace("\n", " ")
        safe_change_note = change_note.replace("\t", " ").replace("\n", " ")
        file.write(
            f"{commit}\t{score:.4f}\t"
            f"{_dimension_value(dimension_means, 'COMP'):.4f}\t"
            f"{_dimension_value(dimension_means, 'DEPTH'):.4f}\t"
            f"{_dimension_value(dimension_means, 'INST'):.4f}\t"
            f"{_dimension_value(dimension_means, 'READ'):.4f}\t"
            f"{latency:.3f}\t{agent_tokens}\t{judge_tokens}\t{total_tokens}\t{agent_calls}\t"
            f"{status}\t{safe_description}\t{safe_change_note}\n"
        )


def _write_run_meta(
    out_dir: Path,
    run_id: str,
    commit: str,
    score: float,
    dimension_means: dict,
    latency: float,
    status: str,
    description: str,
    change_note: str,
    diff_summary: str,
    summary_obj: dict | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id,
        "commit": commit,
        "race_score": score,
        "dimension_means": dimension_means,
        "latency_sec": latency,
        "status": status,
        "description": description,
        "change_note": change_note,
        "diff_summary": diff_summary,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_commit_message(
    description: str,
    score: float,
    dimension_means: dict,
    summary: dict,
    out_dir: Path,
) -> str:
    """After the eval finishes, rewrite this round's commit message with the RACE score and per-case detail so `git log` shows the score directly."""
    comp = _dimension_value(dimension_means, "COMP")
    depth = _dimension_value(dimension_means, "DEPTH")
    inst = _dimension_value(dimension_means, "INST")
    read = _dimension_value(dimension_means, "READ")
    agent_tokens = int(summary.get("agent_tokens_total", 0))
    judge_tokens = int(summary.get("judge_tokens_total", 0))
    total_tokens = int(summary.get("tokens_total", agent_tokens + judge_tokens))
    agent_calls = int(summary.get("agent_llm_calls_total", 0))
    latency = float(summary.get("latency_sec", 0))
    subject = (
        f"experiment: RACE {score:.2f} (C{comp:.1f}/D{depth:.1f}/I{inst:.1f}/R{read:.1f}) "
        f"tok={total_tokens} {latency:.0f}s — {description}"
    )

    case_lines = []
    judged_rows = _read_jsonl(out_dir / "judge.jsonl")
    for judged in judged_rows:
        s = judged.get("scores", {})
        usage = judged.get("usage", {}) or {}
        rationale = str(judged.get("rationale", "")).replace("\n", " ").strip()
        if len(rationale) > 120:
            rationale = rationale[:117] + "..."
        case_lines.append(
            f"- {judged.get('id', '?')}: {float(judged.get('race_score', 0.0)):.2f} "
            f"(C{_dimension_value(s, 'COMP'):.0f}/D{_dimension_value(s, 'DEPTH'):.0f}/"
            f"I{_dimension_value(s, 'INST'):.0f}/R{_dimension_value(s, 'READ'):.0f}) "
            f"agent={int(usage.get('agent_tokens', 0))}tok/{usage.get('agent_seconds', 0)}s "
            f"judge={int(usage.get('judge_tokens', 0))}tok "
            f"— {rationale}"
        )

    body_lines = [
        "",
        f"RACE {score:.2f} on {summary.get('count', 0)} cases, "
        f"COMP={comp:.2f} DEPTH={depth:.2f} INST={inst:.2f} READ={read:.2f}, "
        f"latency={latency:.0f}s, agent_tokens={agent_tokens}, judge_tokens={judge_tokens}, "
        f"total_tokens={total_tokens}, agent_llm_calls={agent_calls}.",
        "",
        f"Out dir: {out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir}",
        "",
        "Per case:",
        *case_lines,
    ]
    return subject + "\n" + "\n".join(body_lines)


def _build_change_note(commit: str, description: str) -> str:
    if not commit:
        return f"{description}; no code change detected in `deepresearch_agent.py` this round."

    diff = _git(["show", "--format=", "--no-renames", "--", "deepresearch_agent.py"], check=False)
    notes = []
    if "system_prompt" in diff or "_main_agent_prompt" in diff:
        notes.append("adjusted main agent system prompt or task organization")
    if "_subagent_prompt" in diff:
        notes.append("adjusted research subagent prompt")
    if "tavily_search" in diff or "TAVILY_" in diff:
        notes.append("adjusted Tavily search tool or parameters")
    if "research_subagent" in diff:
        notes.append("adjusted how the main agent invokes the research subagent")
    if "ResearchState" in diff or "state_schema" in diff or "Command(" in diff:
        notes.append("adjusted LangGraph state or tool-return state updates")
    if "temperature" in diff or "max_tokens" in diff or "MAX_TOKENS" in diff:
        notes.append("adjusted model generation parameters")
    if "citation" in diff or "citations" in diff or "S1" in diff:
        notes.append("adjusted citation or evidence presentation")

    if not notes:
        stats = _git(["show", "--stat", "--format=", "--no-renames", "--", "deepresearch_agent.py"], check=False).strip()
        notes.append("modified deep research agent implementation details")
        if stats:
            notes.append(stats.replace("\n", "; "))

    return f"{description}; " + "; ".join(dict.fromkeys(notes)) + "."


_HTML_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: #1a202c; background: #f6f7f9;
  line-height: 1.55; font-size: 15px;
}
.page { display: grid; grid-template-columns: 240px 1fr; gap: 24px; max-width: 1200px; margin: 0 auto; padding: 24px; }
@media (max-width: 800px) {
  .page { grid-template-columns: 1fr; }
  .toc { position: static !important; max-height: none !important; }
}
header { grid-column: 1 / -1; display: flex; align-items: baseline; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid #e4e7ec; flex-wrap: wrap; gap: 8px; }
header h1 { margin: 0; font-size: 22px; font-weight: 600; }
header .updated { color: #6b7280; font-size: 13px; }
.toc { position: sticky; top: 24px; align-self: start; max-height: calc(100vh - 48px); overflow-y: auto; background: white; border: 1px solid #e4e7ec; border-radius: 10px; padding: 10px; }
.toc h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280; margin: 4px 6px 8px; }
.toc-item { display: grid; grid-template-columns: 32px 1fr auto; gap: 8px; align-items: center; padding: 7px 8px; border-radius: 6px; text-decoration: none; color: #1a202c; font-size: 13px; transition: background 0.15s; }
.toc-item:hover { background: #f6f7f9; }
.toc-num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #6b7280; font-size: 12px; }
.toc-score { font-weight: 600; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.toc-status { font-size: 10px; padding: 1px 6px; border-radius: 999px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.s-improved { background: #dcfce7; color: #16a34a; }
.s-recorded { background: #e2e8f0; color: #475569; }
.s-crash { background: #fee2e2; color: #dc2626; }
main { min-width: 0; }
.card { background: white; border: 1px solid #e4e7ec; border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; }
.overview .top { display: flex; gap: 32px; align-items: baseline; flex-wrap: wrap; margin-bottom: 14px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat-value { font-size: 32px; font-weight: 700; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.stat-value.big { color: #16a34a; }
.stat-label { color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
.dim-row { display: grid; grid-template-columns: 56px 1fr 44px; gap: 10px; align-items: center; margin: 5px 0; font-size: 13px; }
.dim-label { color: #6b7280; font-weight: 600; font-size: 11px; letter-spacing: 0.05em; }
.dim-track { height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; background: linear-gradient(90deg, #60a5fa, #3b82f6); border-radius: 4px; transition: width 0.3s; }
.dim-value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; text-align: right; }
.chart { margin-top: 14px; }
.chart svg { width: 100%; height: 220px; display: block; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 18px; justify-content: center; margin-top: 6px; font-size: 12px; color: #475569; }
.cl-item { display: inline-flex; align-items: center; gap: 6px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 600; }
.cl-line { display: inline-block; width: 16px; height: 3px; border-radius: 1px; }
.cl-line.race { background: #0f172a; height: 4px; }
.cl-line.comp { background: #3b82f6; }
.cl-line.depth { background: #a855f7; }
.cl-line.inst { background: #f59e0b; }
.cl-line.read { background: #10b981; }
.intro { margin: 14px 0 10px; font-size: 13px; color: #475569; line-height: 1.65; }
.intro p { margin: 0 0 10px; }
.intro a { color: #2563eb; text-decoration: none; }
.intro a:hover { text-decoration: underline; }
.legend { display: grid; grid-template-columns: 1fr; gap: 4px; font-size: 12px; }
.legend-row { display: flex; align-items: baseline; gap: 8px; }
.legend-row strong { color: #1a202c; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 700; min-width: 48px; }
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; align-self: center; }
.swatch.race { background: #0f172a; }
.swatch.comp { background: #3b82f6; }
.swatch.depth { background: #a855f7; }
.swatch.inst { background: #f59e0b; }
.swatch.read { background: #10b981; }
.run-card { scroll-margin-top: 24px; }
.run-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
.run-title { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.run-num { font-size: 17px; font-weight: 700; }
.run-id, .run-commit { color: #6b7280; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.run-score { display: flex; align-items: baseline; gap: 10px; }
.run-race { font-size: 26px; font-weight: 700; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.run-race.improved { color: #16a34a; }
.status-pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.desc { margin: 6px 0 12px; }
.meta-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.chip { font-size: 12px; color: #475569; background: #f1f5f9; padding: 3px 10px; border-radius: 999px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.dims-mini { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 18px; margin: 10px 0; }
details { margin-top: 8px; border-top: 1px solid #e4e7ec; padding-top: 8px; }
details > summary { cursor: pointer; font-weight: 600; font-size: 13px; color: #475569; list-style: none; padding: 4px 0; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "▸ "; display: inline-block; color: #6b7280; }
details[open] > summary::before { content: "▾ "; }
pre { white-space: pre-wrap; word-wrap: break-word; background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 8px; overflow: auto; font-size: 12px; line-height: 1.5; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.case { margin-top: 6px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.case > summary { color: #1a202c; font-weight: 500; }
.case-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 700; }
.case-race { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #2563eb; font-weight: 700; margin-left: 8px; }
.case-dims { font-size: 12px; color: #6b7280; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin-left: 8px; }
.rationale { font-size: 13px; color: #475569; margin: 4px 0 8px; padding-left: 12px; border-left: 2px solid #e4e7ec; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0a0e14; }
  .card, .toc { background: #161b22; border-color: #30363d; }
  header { border-color: #30363d; }
  .toc-item { color: #e6edf3; }
  .toc-item:hover { background: #0a0e14; }
  .toc-num, .toc h2, .stat-label, .dim-label, .run-id, .run-commit { color: #8b949e; }
  .chip { background: #21262d; color: #8b949e; }
  .dim-track { background: #21262d; }
  details, .case { border-color: #30363d; }
  details > summary { color: #8b949e; }
  .case > summary { color: #e6edf3; }
  .rationale { color: #8b949e; border-color: #30363d; }
  .s-recorded { background: #21262d; color: #8b949e; }
  .s-improved { background: #033a16; color: #4ade80; }
  .s-crash { background: #3a0d12; color: #f87171; }
  .stat-value.big, .run-race.improved { color: #4ade80; }
  pre { background: #010409; color: #c9d1d9; }
  .intro { color: #8b949e; }
  .intro a { color: #58a6ff; }
  .legend-row strong { color: #e6edf3; }
  .swatch.race { background: #e6edf3; }
  .chart-legend { color: #8b949e; }
  .cl-line.race { background: #e6edf3; }
}
"""


def _write_html_report() -> None:
    runs = _collect_runs()
    best = max((float(run.get("race_score", 0.0)) for run in runs), default=0.0)

    toc_items = "\n".join(
        f'<a class="toc-item" href="#run-{_e(run.get("run_id", ""))}">'
        f'<span class="toc-num">R{i + 1}</span>'
        f'<span class="toc-score">{float(run.get("race_score", 0.0)):.2f}{" ★" if float(run.get("race_score", 0.0)) == best and best > 0 else ""}</span>'
        f'<span class="toc-status s-{_e(run.get("status", ""))}">{_e(run.get("status", ""))}</span>'
        f"</a>"
        for i, run in enumerate(runs)
    )

    chart_svg = _render_chart(runs)
    chart_legend_html = (
        '<div class="chart-legend">'
        '<span class="cl-item"><span class="cl-line race"></span>RACE</span>'
        '<span class="cl-item"><span class="cl-line comp"></span>COMP</span>'
        '<span class="cl-item"><span class="cl-line depth"></span>DEPTH</span>'
        '<span class="cl-item"><span class="cl-line inst"></span>INST</span>'
        '<span class="cl-item"><span class="cl-line read"></span>READ</span>'
        '</div>'
    ) if len(runs) >= 2 else ""
    cards = "\n".join(_render_run(run, i + 1, best) for i, run in enumerate(runs))

    intro_html = (
        '<div class="intro">'
        '<p>Each round\'s <strong>5 fixed test cases</strong> are scored by an LLM judge on a 1–5 scale '
        'along 4 dimensions, derived from '
        '<a href="https://arxiv.org/abs/2506.11763" target="_blank" rel="noopener">DeepResearch Bench</a>\'s '
        'RACE framework (Reference-based Adaptive Criteria-driven Evaluation). '
        '<strong>RACE</strong> = mean of the 4 dimensions per case, averaged over cases.</p>'
        '<div class="legend">'
        '<div class="legend-row"><span class="swatch race"></span><strong>RACE</strong> overall (mean of the 4 below)</div>'
        '<div class="legend-row"><span class="swatch comp"></span><strong>COMP</strong> comprehensiveness — covers the question and reference\'s key points</div>'
        '<div class="legend-row"><span class="swatch depth"></span><strong>DEPTH</strong> insight — analysis, trade-offs, stated limitations</div>'
        '<div class="legend-row"><span class="swatch inst"></span><strong>INST</strong> instruction following — direct answer, obeys task requirements</div>'
        '<div class="legend-row"><span class="swatch read"></span><strong>READ</strong> readability — clear structure and expression</div>'
        '</div>'
        '</div>'
    )

    REPORT_HTML.parent.mkdir(parents=True, exist_ok=True)
    REPORT_HTML.write_text(
        '<!doctype html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <title>AutoDeepResearch · Experiment Report</title>\n'
        f'  <style>{_HTML_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        '  <div class="page">\n'
        '    <header>\n'
        '      <h1>AutoDeepResearch · Experiment Report</h1>\n'
        f'      <span class="updated">Updated {_e(time.strftime("%Y-%m-%d %H:%M:%S"))}</span>\n'
        '    </header>\n'
        f'    <nav class="toc"><h2>Rounds ({len(runs)})</h2>{toc_items}</nav>\n'
        '    <main>\n'
        '      <section class="card overview">\n'
        '        <div class="top">\n'
        f'          <div class="stat"><span class="stat-value big">{best:.2f}</span><span class="stat-label">Best RACE</span></div>\n'
        f'          <div class="stat"><span class="stat-value">{len(runs)}</span><span class="stat-label">Rounds</span></div>\n'
        '        </div>\n'
        f'        {intro_html}\n'
        f'        <div class="chart">{chart_svg}</div>\n'
        f'        {chart_legend_html}\n'
        '      </section>\n'
        f'      {cards}\n'
        '    </main>\n'
        '  </div>\n'
        '</body>\n'
        '</html>\n',
        encoding="utf-8",
    )


def _render_chart(runs: list[dict]) -> str:
    if len(runs) < 2:
        return ""
    n = len(runs)
    statuses = [r.get("status", "") for r in runs]
    series = [
        ("COMP", "#3b82f6", 1.4, [_dimension_value(r.get("dimension_means", {}), "COMP") for r in runs]),
        ("DEPTH", "#a855f7", 1.4, [_dimension_value(r.get("dimension_means", {}), "DEPTH") for r in runs]),
        ("INST", "#f59e0b", 1.4, [_dimension_value(r.get("dimension_means", {}), "INST") for r in runs]),
        ("READ", "#10b981", 1.4, [_dimension_value(r.get("dimension_means", {}), "READ") for r in runs]),
        ("RACE", "#0f172a", 2.6, [float(r.get("race_score", 0.0)) for r in runs]),
    ]

    W, H = 600, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 32, 16, 14, 26
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    def x(i: int) -> float:
        return PAD_L + (plot_w * i / max(n - 1, 1))

    def y(s: float) -> float:
        return PAD_T + plot_h * (1 - s / 5.0)

    grid = "".join(
        f'<line x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e4e7ec" stroke-dasharray="2,4" />'
        f'<text x="{PAD_L - 4}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{v}</text>'
        for v in (1, 2, 3, 4, 5)
    )

    lines = ""
    for _label, color, width, scores in series:
        points = " ".join(f"{x(i):.1f},{y(s):.1f}" for i, s in enumerate(scores))
        lines += (
            f'<polyline points="{points}" stroke="{color}" stroke-width="{width}" '
            f'fill="none" stroke-linejoin="round" />'
        )

    # Only RACE line gets dots; improved rounds highlighted green.
    race_scores = series[-1][3]
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(s):.1f}" '
        f'r="{4 if statuses[i] == "improved" else 3}" '
        f'fill="{"#16a34a" if statuses[i] == "improved" else "#0f172a"}" />'
        for i, s in enumerate(race_scores)
    )

    x_labels = "".join(
        f'<text x="{x(i):.1f}" y="{H - 8}" text-anchor="middle" font-size="9" fill="#94a3b8">R{i + 1}</text>'
        for i in range(n)
    )
    return (
        f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">'
        f"{grid}{lines}{dots}{x_labels}"
        "</svg>"
    )


def _collect_runs() -> list[dict]:
    run_dirs = sorted((ROOT / "experiments" / "runs").glob("*"))
    runs = []
    for run_dir in run_dirs:
        if not run_dir.is_dir():
            continue
        meta = _read_json(run_dir / "run_meta.json") or {"run_id": run_dir.name}
        summary = _read_json(run_dir / "summary.json") or {}
        answers = _read_jsonl(run_dir / "answers.jsonl")
        judged = _read_jsonl(run_dir / "judge.jsonl")
        meta.setdefault("race_score", summary.get("race_score_mean", 0.0))
        meta.setdefault("dimension_means", summary.get("dimension_means", _dimension_means(judged)))
        meta.setdefault("latency_sec", summary.get("latency_sec", 0.0))
        meta.setdefault("change_note", meta.get("description", ""))
        meta["summary"] = summary
        meta["answers"] = answers
        meta["judged"] = judged
        runs.append(meta)
    return runs


def _render_run(run: dict, num: int, best: float) -> str:
    run_id = run.get("run_id", "")
    status = run.get("status", "")
    race = float(run.get("race_score", 0.0))
    is_best = race == best and best > 0
    commit_short = str(run.get("commit", ""))[:10]
    dim_means = run.get("dimension_means", {})

    dim_html = "".join(
        f'<div class="dim-row"><span class="dim-label">{name}</span>'
        f'<div class="dim-track"><div class="dim-fill" style="width:{_dimension_value(dim_means, name) / 5 * 100:.1f}%"></div></div>'
        f'<span class="dim-value">{_dimension_value(dim_means, name):.2f}</span></div>'
        for name in ("COMP", "DEPTH", "INST", "READ")
    )

    summary = run.get("summary", {})
    total_tokens = int(summary.get("tokens_total", 0))
    agent_calls = int(summary.get("agent_llm_calls_total", 0))
    latency = float(run.get("latency_sec", 0.0))
    chips = []
    if latency > 0:
        chips.append(f'<span class="chip">latency {latency:.0f}s</span>')
    if total_tokens > 0:
        chips.append(f'<span class="chip">tokens {total_tokens:,}</span>')
    if agent_calls > 0:
        chips.append(f'<span class="chip">llm calls {agent_calls}</span>')
    chips_html = '<div class="meta-chips">' + "".join(chips) + "</div>" if chips else ""

    cases_html = []
    for answer, judged in zip(run.get("answers", []), run.get("judged", [])):
        scores = judged.get("scores", {})
        case_race = float(judged.get("race_score", 0.0))
        cases_html.append(
            f'<details class="case">'
            f"<summary>"
            f'<span class="case-id">{_e(answer.get("id", "case"))}</span>'
            f'<span class="case-race">RACE {case_race:.2f}</span>'
            f'<span class="case-dims">C{scores.get("COMP", "-")} D{scores.get("DEPTH", "-")} I{scores.get("INST", "-")} R{scores.get("READ", "-")}</span>'
            f"</summary>"
            f'<p class="rationale">{_e(judged.get("rationale", ""))}</p>'
            f"<pre>{_e(answer.get('answer', ''))}</pre>"
            f"</details>"
        )

    star = " ★" if is_best else ""
    race_class = " improved" if status == "improved" else ""
    return (
        f'<section class="card run-card" id="run-{_e(run_id)}">'
        f'<div class="run-header">'
        f'<div class="run-title">'
        f'<span class="run-num">Round {num}{star}</span>'
        f'<span class="run-id">{_e(run_id)}</span>'
        f'<span class="run-commit">{_e(commit_short)}</span>'
        f'</div>'
        f'<div class="run-score">'
        f'<span class="run-race{race_class}">{race:.2f}</span>'
        f'<span class="status-pill s-{_e(status)}">{_e(status)}</span>'
        f'</div>'
        f'</div>'
        f'<p class="desc">{_e(run.get("change_note", run.get("description", "")))}</p>'
        f"{chips_html}"
        f'<div class="dims-mini">{dim_html}</div>'
        f"<details><summary>Code diff</summary><pre>{_e(run.get('diff_summary', ''))}</pre></details>"
        f'<details><summary>Cases ({len(cases_html)})</summary>{"".join(cases_html)}</details>'
        f"</section>"
    )


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _dimension_means(judged: list[dict]) -> dict[str, float]:
    if not judged:
        return {"COMP": 0.0, "DEPTH": 0.0, "INST": 0.0, "READ": 0.0}
    means = {}
    for name in ("COMP", "DEPTH", "INST", "READ"):
        means[name] = sum(float(item.get("scores", {}).get(name, 0.0)) for item in judged) / len(judged)
    return means


def _best_dimension_means(runs: list[dict]) -> dict[str, float]:
    if not runs:
        return {"COMP": 0.0, "DEPTH": 0.0, "INST": 0.0, "READ": 0.0}
    best_run = max(runs, key=lambda run: float(run.get("race_score", 0.0)))
    return {name: _dimension_value(best_run.get("dimension_means", {}), name) for name in ("COMP", "DEPTH", "INST", "READ")}


def _dimension_value(dimension_means: dict, name: str) -> float:
    try:
        return float(dimension_means.get(name, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _git(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
