from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from deepresearch_agent import run_deepresearch

from langchain_core.callbacks.base import BaseCallbackHandler


RACE_DIMENSIONS = ("COMP", "DEPTH", "INST", "READ")


class TokenCounter(BaseCallbackHandler):
    """Accumulate token usage across all LLM calls. Thread-safe when one instance is used per sample."""

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def on_llm_end(self, response, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.calls += 1
        # langchain_openai puts usage either in LLMResult.llm_output['token_usage'] or in each generation's message.usage_metadata
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") if isinstance(llm_output, dict) else None
        if usage:
            self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            self.total_tokens += int(usage.get("total_tokens", 0) or 0)
            return
        # fallback: walk generations[*].message.usage_metadata
        for batch in getattr(response, "generations", []) or []:
            for gen in batch:
                msg = getattr(gen, "message", None)
                meta = getattr(msg, "usage_metadata", None) if msg else None
                if not meta:
                    continue
                self.prompt_tokens += int(meta.get("input_tokens", 0) or 0)
                self.completion_tokens += int(meta.get("output_tokens", 0) or 0)
                self.total_tokens += int(meta.get("total_tokens", 0) or 0)
JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
BASE_URL = os.getenv("OPENAI_BASE_URL")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "dataset.jsonl"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else ROOT / "experiments" / "runs" / time.strftime("%Y%m%d-%H%M%S")
    summary = run_eval(Path(args.dataset), args.limit, out_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_eval(dataset_path: Path, limit: int, out_dir: Path) -> dict[str, Any]:
    samples = _load_jsonl(dataset_path)[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    judge_path = out_dir / "judge.jsonl"
    answer_path = out_dir / "answers.jsonl"
    started = time.time()
    max_workers = _eval_workers(len(samples))

    evaluated = [None] * len(samples)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(_eval_sample, sample): index
            for index, sample in enumerate(samples)
        }
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            evaluated[index] = future.result()

    results = []
    with judge_path.open("w", encoding="utf-8") as judge_file, answer_path.open("w", encoding="utf-8") as answer_file:
        for item, judged in evaluated:
            answer_file.write(json.dumps(item, ensure_ascii=False) + "\n")
            judge_file.write(json.dumps(judged, ensure_ascii=False) + "\n")
            results.append(judged)

    summary = summarize_scores(results)
    summary["latency_sec"] = round(time.time() - started, 3)
    summary["out_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _eval_sample(sample: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    counter = TokenCounter()
    started = time.time()
    agent_result = run_deepresearch(sample["question"], sample.get("source_notes", []), callbacks=[counter])
    agent_seconds = time.time() - started

    answer = str(agent_result.get("answer", ""))
    judge_tokens = {"prompt": 0, "completion": 0, "total": 0}
    judge_started = time.time()
    judge_result = judge_answer(sample, answer, judge_tokens)
    judge_seconds = time.time() - judge_started

    usage = {
        "agent_tokens": counter.total_tokens,
        "agent_prompt_tokens": counter.prompt_tokens,
        "agent_completion_tokens": counter.completion_tokens,
        "agent_llm_calls": counter.calls,
        "agent_seconds": round(agent_seconds, 2),
        "judge_tokens": judge_tokens["total"],
        "judge_prompt_tokens": judge_tokens["prompt"],
        "judge_completion_tokens": judge_tokens["completion"],
        "judge_seconds": round(judge_seconds, 2),
        "total_tokens": counter.total_tokens + judge_tokens["total"],
        "total_seconds": round(agent_seconds + judge_seconds, 2),
    }
    item = {
        "id": sample["id"],
        "answer": answer,
        "trace": agent_result.get("trace", {}),
        "usage": usage,
    }
    judged = {
        "id": sample["id"],
        "scores": judge_result["scores"],
        "race_score": judge_result["race_score"],
        "rationale": judge_result.get("rationale", ""),
        "usage": usage,
    }
    return item, judged


def _eval_workers(sample_count: int) -> int:
    configured = int(os.getenv("EVAL_MAX_WORKERS", "0") or "0")
    if configured > 0:
        return max(1, min(configured, sample_count or 1))
    return max(1, sample_count)


def judge_answer(sample: dict[str, Any], answer: str, token_out: dict[str, int] | None = None) -> dict[str, Any]:
    prompt = _build_judge_prompt(sample, answer)
    raw = _call_judge_model(prompt, token_out=token_out)
    parsed = _parse_judge_json(raw)
    if parsed is None:
        parsed = _fallback_judge(sample, answer)
    parsed["race_score"] = race_score(parsed)
    return parsed


def race_score(judge_result: dict[str, Any]) -> float:
    scores = judge_result.get("scores", {})
    values = [float(scores[name]) for name in RACE_DIMENSIONS if name in scores]
    if not values:
        return 0.0
    return sum(values) / len(values)


def summarize_scores(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"race_score_mean": 0.0, "dimension_means": {name: 0.0 for name in RACE_DIMENSIONS}, "count": 0}
    total = sum(float(item["race_score"]) for item in results)
    dimension_means = {}
    for name in RACE_DIMENSIONS:
        dimension_total = sum(float(item.get("scores", {}).get(name, 0.0)) for item in results)
        dimension_means[name] = dimension_total / len(results)
    agent_tokens_sum = sum(int(item.get("usage", {}).get("agent_tokens", 0)) for item in results)
    judge_tokens_sum = sum(int(item.get("usage", {}).get("judge_tokens", 0)) for item in results)
    agent_calls_sum = sum(int(item.get("usage", {}).get("agent_llm_calls", 0)) for item in results)
    return {
        "race_score_mean": total / len(results),
        "dimension_means": dimension_means,
        "count": len(results),
        "agent_tokens_total": agent_tokens_sum,
        "judge_tokens_total": judge_tokens_sum,
        "tokens_total": agent_tokens_sum + judge_tokens_sum,
        "agent_llm_calls_total": agent_calls_sum,
    }


def _build_judge_prompt(sample: dict[str, Any], answer: str) -> str:
    return f"""You are a deep research evaluator. Score the candidate answer following the spirit of DeepResearch Bench's RACE framework, simplified.

RACE = Reference-based Adaptive Criteria-driven Evaluation framework with Dynamic Weighting.
This project's first version uses four fixed dimensions, each scored 1 to 5:
- COMP: comprehensiveness — does it cover the question and the reference answer's key points?
- DEPTH: insight and depth — is there analysis, trade-offs, and stated limitations?
- INST: instruction following — does it answer the question directly and obey the task requirements?
- READ: readability — are the structure and expression clear?

Output JSON only. Do not output Markdown.

JSON format:
{{
  "scores": {{"COMP": 1, "DEPTH": 1, "INST": 1, "READ": 1}},
  "rationale": "short rationale, in the same language as the candidate answer"
}}

Question:
{sample["question"]}

Reference answer:
{sample["reference"]}

Must cover:
{json.dumps(sample.get("must_cover", []), ensure_ascii=False)}

Source notes:
{json.dumps(sample.get("source_notes", []), ensure_ascii=False)}

Candidate answer:
{answer}
"""


def _call_judge_model(prompt: str, token_out: dict[str, int] | None = None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""
    try:
        from openai import OpenAI
    except ImportError:
        return ""
    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0.0,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"thinking": {"type": "disabled"}},
    )
    if token_out is not None and getattr(response, "usage", None):
        token_out["prompt"] = int(getattr(response.usage, "prompt_tokens", 0) or 0)
        token_out["completion"] = int(getattr(response.usage, "completion_tokens", 0) or 0)
        token_out["total"] = int(getattr(response.usage, "total_tokens", 0) or 0)
    return response.choices[0].message.content or ""


def _parse_judge_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    scores = data.get("scores")
    if not isinstance(scores, dict):
        return None
    clean_scores: dict[str, float] = {}
    for name in RACE_DIMENSIONS:
        value = float(scores.get(name, 1))
        clean_scores[name] = max(1.0, min(5.0, value))
    return {"scores": clean_scores, "rationale": str(data.get("rationale", ""))}


def _fallback_judge(sample: dict[str, Any], answer: str) -> dict[str, Any]:
    text = answer.lower()
    must_cover = sample.get("must_cover", [])
    covered = sum(1 for item in must_cover if str(item).lower() in text)
    coverage_ratio = covered / max(1, len(must_cover))
    base = 2.0 + 3.0 * coverage_ratio
    length_bonus = 0.5 if len(answer) >= 120 else 0.0
    scores = {
        "COMP": _clamp(base),
        "DEPTH": _clamp(2.5 + length_bonus),
        "INST": _clamp(3.5 if answer.strip() else 1.0),
        "READ": _clamp(3.5 if "\n" in answer or "。" in answer else 2.5),
    }
    return {
        "scores": scores,
        "rationale": "Model API not configured; using local fallback scoring (smoke test only).",
    }


def _clamp(value: float) -> float:
    return max(1.0, min(5.0, round(value, 2)))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
