"""Minimal deep research agent.

The auto-experimenter should only modify this file. External eval
scripts depend only on the stable `run_deepresearch(question, source_notes)`
entry point.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import operator
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph.message import add_messages
from langgraph.types import Command
from typing_extensions import Annotated, TypedDict


load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
BASE_URL = os.getenv("OPENAI_BASE_URL")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_SEARCH_URL = os.getenv("TAVILY_SEARCH_URL", "https://api.tavily.com/search")
TAVILY_SEARCH_DEPTH = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
TAVILY_MAX_RESULTS = max(int(os.getenv("TAVILY_MAX_RESULTS", "5")), 5)
MAX_TOKENS = 32000
RECURSION_LIMIT = 100
SYNTHESIS_PROMPT_VERSION = "v1-minimal-prompts"
MODEL_EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "disabled"}}


class ResearchState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    research_path: Annotated[list[dict[str, Any]], operator.add]
    search_queries: Annotated[list[str], operator.add]
    search_results: Annotated[list[dict[str, Any]], operator.add]


class ToolBindableFakeChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[no-untyped-def]
        return self


def run_deepresearch(
    question: str,
    source_notes: list[str],
    callbacks: list | None = None,
) -> dict[str, Any]:
    graph = build_graph()
    invoke_config: dict[str, Any] = {"recursion_limit": RECURSION_LIMIT}
    if callbacks:
        invoke_config["callbacks"] = callbacks
    result = graph.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "source_notes": source_notes},
                        ensure_ascii=False,
                    ),
                }
            ]
        },
        config=invoke_config,
    )
    research_path = result.get("research_path", [])
    search_results = _collect_search_results(research_path)
    return {
        "answer": result["messages"][-1].content,
        "citations": [
            {"id": item["id"], "title": item["title"], "url": item["url"]}
            for item in search_results
        ],
        "trace": {
            "research_path": research_path,
            "search_provider": "tavily_search" if TAVILY_API_KEY else "none",
            "synthesis_prompt_version": SYNTHESIS_PROMPT_VERSION,
        },
    }


def build_graph():
    """Build the LangGraph with one main agent and one research subagent."""
    sub_agent = create_agent(
        _make_llm(role="subagent", temperature=0.2),
        tools=[tavily_search],
        state_schema=ResearchState,
        system_prompt=_subagent_prompt(),
    )

    @tool
    def research_subagent(prompt: str, runtime: ToolRuntime) -> str:
        """
        Invoke the research subagent; the subagent can use the Tavily search tool.

        Args:
            prompt: the full research task to hand to the subagent.
            runtime: the tool runtime context.

        Returns:
            The subagent's research findings.
        """
        prior_path = runtime.state.get("research_path", []) if runtime.state else []
        offset = sum(len(p.get("search_results", [])) for p in prior_path)

        result = sub_agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": RECURSION_LIMIT},
        )
        sub_results = result.get("search_results", [])
        answer = result["messages"][-1].content
        remapped_results, remapped_answer = _remap_citation_ids(sub_results, answer, offset)
        research_path = {
            "research_prompt": prompt,
            "research_answer": remapped_answer,
            "search_queries": result.get("search_queries", []),
            "search_results": remapped_results,
        }
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=remapped_answer,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
                "research_path": [research_path],
            }
        )

    return create_agent(
        _make_llm(role="main", temperature=0.25),
        tools=[research_subagent],
        state_schema=ResearchState,
        system_prompt=_main_agent_prompt(),
    )


@tool
def tavily_search(query: str, runtime: ToolRuntime) -> str:
    """
    Search the web using the Tavily Search API.

    Args:
        query: the search query.
        runtime: the tool runtime context.

    Returns:
        A summary of search results with citation markers.
    """
    results = _tavily_search(query)
    if results:
        content = _format_search_results(results)
    else:
        content = (
            f"NO RESULTS for query: {query!r}. "
            "The web search returned nothing. "
            "Do NOT call tavily_search again with a similar query. "
            "If you have enough information from prior searches, write the final answer now. "
            "If you have no information at all, write the best answer you can from your own knowledge."
        )
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=content,
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "search_queries": [query],
            "search_results": results,
        }
    )


def _make_llm(*, role: str, temperature: float):
    if not os.getenv("OPENAI_API_KEY"):
        if role == "main":
            return ToolBindableFakeChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "research_subagent",
                                "args": {"prompt": "Answer the user's question based on the fixed source materials."},
                                "id": "fallback-research-subagent",
                            }
                        ],
                    ),
                    AIMessage(
                        content="Conclusion: A cautious answer can be formed from the given source materials.\n\nAnalysis: Stay focused on the facts in the materials, covering key evidence, causes, and limitations; remain reserved on claims the materials do not directly support.",
                    ),
                ]
            )
        return ToolBindableFakeChatModel(
            responses=[
                AIMessage(
                    content="Conclusion: The source materials support an initial answer to the question.\nEvidence: prefer facts from the given source_notes.\nUncertainty: do not elaborate on parts not supported by the materials.",
                )
            ]
        )

    kwargs: dict[str, Any] = {
        "model": MODEL,
        "temperature": temperature,
        "max_tokens": MAX_TOKENS,
    }
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    if MODEL_EXTRA_BODY:
        kwargs["extra_body"] = MODEL_EXTRA_BODY
    return ChatOpenAI(**kwargs)


def _tavily_search(query: str) -> list[dict[str, Any]]:
    if not TAVILY_API_KEY:
        return []

    body = {
        "query": query,
        "search_depth": TAVILY_SEARCH_DEPTH,
        "max_results": max(1, min(TAVILY_MAX_RESULTS, 20)),
        "include_answer": False,
        "include_raw_content": False,
        "include_usage": True,
    }
    request = urllib.request.Request(
        TAVILY_SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {TAVILY_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    results: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        url_value = str(item.get("url", "")).strip()
        if not url_value:
            continue
        content = str(item.get("content", "")).strip()
        results.append(
            {
                "id": f"S{len(results) + 1}",
                "title": str(item.get("title", "")).strip(),
                "url": url_value,
                "snippets": [content] if content else [],
                "score": item.get("score"),
            }
        )
    return results


def _main_agent_prompt() -> str:
    return """You are the main agent of a deep research system.

Workflow:
1. Read the question carefully and identify ALL the key sub-topics it requires —
   including less-obvious aspects like specific technology categories, edge cases,
   or practical constraints explicitly or implicitly mentioned.
   Then call `research_subagent` 2-3 times, each covering a different named group
   of sub-topics. Make sure ALL identified sub-topics are assigned to a subagent call.
1.5. After gathering research, review your identified sub-topics and verify:
   (a) each important sub-topic has evidence, (b) long-term or future implications
   are addressed where relevant, (c) 'why' motivations are covered alongside
   'how' mechanisms. If any gap exists, call `research_subagent` once more
   targeting that specific gap before writing the final answer.
2. Write the final answer as a single plain-text message. Never return empty content.
   Include analysis of trade-offs, limitations, and open questions relevant to the topic.
   For each key named method or technology, briefly explain its theoretical basis or
   mechanism of operation, not just its practical use.
"""


def _subagent_prompt() -> str:
    return """You are the research subagent.

Workflow:
1. Call `tavily_search` 2-3 times using DIFFERENT search angles, for example:
   (a) practical tools and implementations, (b) theoretical foundations or mathematical
   principles, (c) comparative studies or surveys of existing projects,
   (d) long-term trends or future implications.
2. If tavily_search returns "NO RESULTS", stop immediately and write your answer from your own knowledge.
3. Emit a single plain-text final message. Never return empty content.
"""


def _remap_citation_ids(
    results: list[dict[str, Any]], answer: str, offset: int
) -> tuple[list[dict[str, Any]], str]:
    """Remap this subagent call's [S1]..[SN] to globally-unique [S(1+offset)]..[S(N+offset)]."""
    if offset <= 0 or not results:
        return results, answer
    id_map: dict[str, str] = {}
    new_results: list[dict[str, Any]] = []
    for idx, item in enumerate(results, start=1):
        new_id = f"S{idx + offset}"
        id_map[f"S{idx}"] = new_id
        new_item = dict(item)
        new_item["id"] = new_id
        new_results.append(new_item)

    def _replace(match: re.Match[str]) -> str:
        token = match.group(1)
        return f"[{id_map.get(token, token)}]"

    new_answer = re.sub(r"\[(S\d+)\]", _replace, answer)
    return new_results, new_answer


def _format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No web search results."
    blocks = []
    for result in results:
        snippets = "\n".join(f"  - {snippet}" for snippet in result.get("snippets", []))
        blocks.append(
            f"[{result['id']}] {result.get('title', '')}\nURL: {result.get('url', '')}\nExcerpts:\n{snippets or '  - no excerpts'}"
        )
    return "\n\n".join(blocks)


def _collect_search_results(research_path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for path in research_path:
        for result in path.get("search_results", []):
            url_value = result.get("url", "")
            if url_value in seen_urls:
                continue
            seen_urls.add(url_value)
            collected.append(dict(result))
    return collected
