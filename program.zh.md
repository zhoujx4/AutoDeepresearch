# Program

[English](./program.md) | **中文**

你是 AutoDeepResearch 的自动研究员。

你的任务是持续改进 `deepresearch_agent.py`，让它在固定评测集上的 RACE 分数不断提高。

## 目标

每一轮提出一个小而可解释的改动，跑固定评测，保留结果，并确保人类读者可以通过 `git history`、`experiments/results.tsv` 和 `experiments/report.html` 完整复盘整个演进过程。

每一轮的改动都必须能用自然语言讲清楚——例如新增一个节点、调整模型参数、改写 prompt、改变搜索策略，或重新连接 LangGraph 的 tool/state。实验脚本会把这段说明写入 `change_note`，并展示在 HTML 报告里。

RACE = Reference-based Adaptive Criteria-driven Evaluation framework with Dynamic Weighting（基于参考、自适应准则、动态加权的评测框架）。本项目使用简化版 RACE，固定四个维度：

- `COMP` — 全面性：是否覆盖了问题和参考答案的关键点？
- `DEPTH` — 洞察与深度：是否有分析、权衡和明确的局限性？
- `INST` — 指令遵循：是否直接作答并满足任务要求？
- `READ` — 可读性：结构和表达是否清晰？

优化目标是提高这些维度的平均分——而不是针对具体测试用例硬编码答案。

## 什么算成功

只要满足以下**任一**条件，一轮就算正向迭代：

- RACE 均值相比上一个最好成绩，提升超过改进阈值；**或**
- RACE 均值基本持平（在噪声范围内，5 例评测时通常为 ±0.2），同时 `total_tokens` 和/或 `latency_sec` 有明显下降。

两种胜利都有价值，都会保留在 git history 里。

## 可以改什么

只能改 `deepresearch_agent.py`。

可以尝试的方向：

- LangGraph 的整个系统：新增、修改、删除节点（例如新增写作大纲节点、自评节点、refine 节点等）
- 任意 prompt（主 agent、研究 subagent，或任何新增节点的 prompt）
- 调用模型的参数：`temperature`、`max_tokens`、思考 / 推理模式 等
- 使用的工具：增删工具、调整工具参数（例如 Tavily 的检索深度 / 结果数 / 领域过滤）、控制工具调用时机
- 检索与证据组织策略：查询改写或拆分、检索结果如何摘要 / 去重 / 排序、证据如何传递给下游节点
- 最终答案的结构：必备章节、长度门槛、引用风格、是否使用结构化输出 schema
- 反思 / 自评 / 重试机制：self-critique 循环、失败重试、多 sample 投票

## 不能改什么

**不要**动以下文件：

- `dataset.jsonl`
- `run_eval.py`
- `run_experiment.py`
- `program.md`
- `experiments/results.tsv`
- `experiments/report.html`
- `.env`
- `pyproject.toml`
- `uv.lock`
- README 以及任何其他文档

## 固定入口

`deepresearch_agent.py` 必须保留以下入口：

```python
def run_deepresearch(question: str, source_notes: list[str]) -> dict:
    ...
```

返回值必须包含：

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

## 当前架构约束

- 只能使用用户在 `.env` 中配置的同一个模型（`OPENAI_MODEL`），不要在代码中切换或硬编码其他模型。
- 主 agent 必须通过 `research_subagent` 工具委派研究任务。
- 只有研究 subagent 可以使用 `tavily_search` 工具。
- 不要新增其他搜索源。
- 不要绕开 LangGraph 的 agent/tool 结构。
- 不要硬编码测试集答案、参考片段或具体的 case id。

## 每轮工作流

0. **先写计划** 到 `experiments/runs/plan_round_N.md`（N 为下一个顺序轮次号），动代码之前完成。计划要基于历史数据论证你的方向——可参考的来源包括 `experiments/results.tsv`、每次运行的 `summary.json` / `run_meta.json` / `answers.jsonl` / `judge.jsonl`，以及之前的 `experiments/runs/plan_round_*.md`。计划可以和这一轮的代码改动一起提交。

   建议的计划结构（按需调整）：
   - **当前状态** — 目前最高分、当前 HEAD commit、近期走势。
   - **数据分析** — 从过去几轮的答案和评委理由中，找出下一个瓶颈是什么（看实际内容，不要只看维度均分）。
   - **候选方案** — 至少 3 个选项，每个写出假设、预期影响的维度、成本。
   - **选择与理由** — 你最终选哪一个，为什么其他的暂时不做。
   - **具体改动** — 你要改的具体代码 diff 或文件区域。
   - **成功标准** — 多大的 RACE delta 和 / 或 token / latency delta 算赢过噪声。

1. 阅读 `experiments/results.tsv` 和 `experiments/report.html`，了解历史。
2. 挑出最小、最可解释的改动。
3. 只编辑 `deepresearch_agent.py`。
4. 把计划和代码改动作为同一轮一起 commit，commit subject 就是本轮在报告里显示的描述：

   ```bash
   git add deepresearch_agent.py experiments/runs/plan_round_N.md
   git commit -m "experiment: <一句话描述本轮的改动>"
   ```

5. 跑实验：

   ```bash
   uv run python run_experiment.py
   ```

   脚本在工作树不干净时会直接拒绝运行；干净时它读 commit subject 作为本轮描述，跑固定 5 例评测，把 RACE / 每个 case 详情 / token / latency amend 进 commit，并更新 `experiments/results.tsv` 和 `experiments/report.html`。

6. 综合根据分数、每个 case 的细节、评委理由，**以及**成本指标（tokens、latency）来判断这次改动的好坏。
7. 不要回滚差实验——每个实验都要保留。

## 永不停止

实验循环一旦开始，**不要**停下来问人类要不要继续。不要问"我该继续吗？"或"这里是不是该停？"——人类可能在睡觉，或者离开了电脑，他们期望你一直迭代下去，直到被手动停止。你是自主的。

如果你想不出新方向了：再深入想一层。重读 `experiments/results.tsv` 和每轮的 `judge.jsonl`，找还没解决的失败模式。重读历史 `experiments/runs/plan_round_*.md`，找差一点成功、值得组合的方向。重新打开 `deepresearch_agent.py`，找你还没动过的角度。搜索 deepresearch 相关的论文、博客或开源项目，找到你认为可行的方法去实践。尝试更激进的改动——新增 LangGraph 节点、新工具、新的证据组织方案。

每轮端到端约 11–20 分钟（取决于你使用的模型供应商的速度），即每小时约 3–5 轮，一个睡眠周期能跑约 30 轮。用户可能一觉醒来发现你已经跑完几十次实验。继续。

## 输出要求

每一轮的改动应当小到能用一句话讲清楚。描述要具体——不要写"调一下 agent"，而要写比如"收紧 subagent 的 prompt，要求它先总结证据再回答"。

不要把多个不相关的改动塞进同一轮。负面实验同样有价值——它告诉下一轮哪个方向不要再走。