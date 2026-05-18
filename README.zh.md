# AutoDeepResearch

[English](./README.md) | **中文**

一个参考 karpathy/autoresearch 思路的极简 deep research agent 自动实验项目。

项目目标：让 LLM 像自动研究员一样，反复修改一个小的 deep research agent，跑固定评测，记录每轮结果，并把好实验和差实验都保留下来。

**[在线实验报告](https://zhoujx4.github.io/AutoDeepresearch/experiments/report.html)** — 每轮的 RACE 分数、case 详情、judge 理由和代码 diff。

## 核心思路

- 可变代码集中在 `deepresearch_agent.py`。
- 评测集固定在 `dataset.jsonl`。
- 评测逻辑固定在 `run_eval.py`。
- 每轮实验只做一个小改动。
- 所有实验都保留为 git commit 和结果记录，不回滚差实验。
- `experiments/report.html` 给人看详细过程，`experiments/results.tsv` 给程序读历史分数。
- 每轮记录不只包含代码 diff，还包含一段自然语言变更说明，写入 `change_note` 并展示在 HTML 报告里。

## Agent 架构

当前 agent 使用 LangGraph / LangChain：

- 主 agent 负责理解问题、组织最终回答。
- 主 agent 只能通过 `research_subagent` 工具调用研究子 agent。
- 研究子 agent 可以调用 `tavily_search` 工具搜索网页。
- 搜索结果用 `S1`、`S2` 这类编号引用。

## 评测方法

**测试集**：5 条题目随机抽自 [DeepResearch Bench](https://github.com/Ayanami0730/deep_research_bench)（RACE 论文 [arXiv:2506.11763](https://arxiv.org/abs/2506.11763)）官方 100 道研究任务，固定在 `dataset.jsonl`。每条带原题 + 官方 reference report + comprehensiveness criterion 提取的 `must_cover` 要点。

**评分框架**：简化版 RACE（Reference-based Adaptive Criteria-driven Evaluation framework with Dynamic Weighting），固定四个维度，每项 1–5 分：

- `COMP`：全面性，是否覆盖问题和 reference 要点
- `DEPTH`：洞察与深度，是否有分析、权衡、限制条件
- `INST`：指令遵循，是否直接回答问题并遵守任务要求
- `READ`：可读性，结构与表达是否清晰

由 LLM judge（`OPENAI_JUDGE_MODEL`）一次性给四维打分 + 简短理由，输出 JSON。RACE 分 = 四维平均。

**成本指标**：每轮同时记录 `latency_sec`、`agent_tokens`、`judge_tokens`、`total_tokens`、`agent_llm_calls`。RACE 不涨但 token / latency 降低也算迭代成功。

## 文件结构

```text
deepresearch_agent.py          被自动研究员改进的 agent
program.md                     给自动研究员看的实验说明
run_eval.py                    固定 RACE 评测入口
run_experiment.py              自动实验编排入口
dataset.jsonl                  固定评测集
experiments/results.tsv        机器可读实验历史
experiments/report.html        人类可读实验报告
.env                           本地环境变量，不提交
.env.example                   环境变量模板
```

## 快速开始

```bash
cd /Users/bytedance/Code/AutoDeepResearch
uv sync
```

复制 `.env.example` 到 `.env`，填入模型和搜索配置：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
TAVILY_API_KEY=...
```

先跑一条 smoke test：

```bash
uv run python run_eval.py --limit 1
```

跑完整 5 条固定评测：

```bash
uv run python run_eval.py --limit 5
```

运行一轮完整实验（对当前 HEAD 跑评测，把 RACE 分数 amend 进 commit，并更新 TSV 和 HTML 报告）：

```bash
git add deepresearch_agent.py experiments/runs/plan_round_N.md
git commit -m "experiment: <一句话描述本轮的改动>"
uv run python run_experiment.py
```

自动研究员（当前对话里的 AI，或者你自己）负责写计划、改 `deepresearch_agent.py`、commit，然后跑 `run_experiment.py`。脚本会读 HEAD commit 的 subject 作为本轮描述；工作树有未提交改动时会直接拒绝运行。

## 实验循环

一轮实验大致是：

```text
读取历史结果与上轮判官理由
  -> 写 experiments/runs/plan_round_N.md
       （现状诊断、候选方向、选择与理由、成功标准）
  -> 修改 deepresearch_agent.py
  -> git commit -m "experiment: <描述>"
  -> 跑 run_experiment.py
       -> 从 HEAD commit subject 读描述
       -> 并行跑 5 条固定 case
       -> RACE judge 打分
       -> 把 RACE / 每个 case 详情 / token / latency amend 进 commit
       -> 追加到 results.tsv，重写 report.html
  -> 下一轮
```

`run_experiment.py` 不会因为分数下降而回滚。分数提升超过阈值的实验标记为 `improved`，其他成功跑完的实验标记为 `recorded`。

## 查看结果

- 打开 `experiments/report.html` 看每轮自然语言变更、代码变化、case 分数、答案和 judge 理由。
- 查看 `experiments/results.tsv` 做趋势分析，其中 `change_note` 列记录每轮改动说明。
- 查看 git history 了解每轮代码变化。
