# Round 5 — Force exactly 3 subagent calls and 3 searches each

## Current state
- Best RACE: 4.35 (Round 4, status=improved)
- Dimension means R4: COMP=3.80, DEPTH=4.20, INST=4.60, READ=4.80

## Data analysis

COMP has not improved across any round (always 3.80). 
In every round, at least 2 cases score COMP=3 due to missing named sub-topics.

Round 4 drb_en_68 regression (4.50→3.50): the "theory vs methods vs implementation"
framing caused the K8s autoscaling answer to over-index on theoretical context and
under-index on specific tool details (non-elastic node groups, spot/reserved/GPU,
cost optimization). The diversification instruction is helpful for broad topics but
can misfire for practical engineering topics.

Round 4 drb_en_100 improvement (3.25→4.00): DEPTH up (3→4), READ up (3→5) —
scope diversification did help. But COMP still 3 (missing relationship types).

Key observation: when "2-3 subagent calls" is specified, the model often chooses 2
(cheaper). When "2-3 searches" is specified, same issue. Getting 3 × 3 = 9 search
queries would cover substantially more ground than the current ~4-6.

## Candidate levers

1. **Force 3 subagent calls × 3 searches each (9 total)** — highest expected
   COMP gain. Cost: ~50% more tokens. Hypothesis: COMP rises from 3.80 to 4.0+.
   **← CHOSEN**

2. **Self-critique step** — after writing, agent lists missing topics and fills gaps.
   High complexity, two extra LLM calls. Defer.

3. **Query diversification instruction in subagent** — tell subagent to vary search
   angle explicitly by dimension (e.g., tools/tech, research papers, case studies).
   Low cost. Could combine with Lever 1.

## Choice + reason
Lever 1. COMP=3.80 is the only major remaining gap. Forcing 9 total searches
(vs current ~4-6) is the most direct way to cover more named sub-topics.
The cost (more tokens) is acceptable given that token count is not the primary
constraint here.

## Specific changes
- `_main_agent_prompt`: "Call `research_subagent` exactly 3 times"
- `_subagent_prompt`: "Call `tavily_search` exactly 3 times using different query angles"

## Success criteria
- RACE mean > 4.40 (beats best of 4.35 by >0.05 → "improved").
- COMP mean > 3.80 (breaking the persistent 3.80 floor).
