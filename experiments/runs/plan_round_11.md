# Round 11 — Default subagent to 3 searches for deeper sub-topic evidence

## Current state
- Best RACE: 4.80 (Round 8 + Round 10 tie, status=recorded for R10)
- Dimension means R10: COMP=4.60, DEPTH=4.60, INST=5.00, READ=5.00

## Data analysis

Round 10 per-case:
| case | RACE | C | D | I | R | gap |
|------|------|---|---|---|---|-----|
| drb_en_60 (cislunar) | 4.50 | 4 | 4 | 5 | 5 | "less emphasis on characterization/ID techniques" |
| drb_en_64 (UAV PID) | 5.00 | 5 | 5 | 5 | 5 | perfect |
| drb_en_68 (K8s auto) | 5.00 | 5 | 5 | 5 | 5 | perfect |
| drb_en_95 (Diamond) | 5.00 | 5 | 5 | 5 | 5 | perfect |
| drb_en_100 (AI) | 4.50 | 4 | 4 | 5 | 5 | "less granular typology; less deep ethical discussion" |

Both weak cases have C=4 due to depth/detail in a specific sub-area, not missing topics.
The agent covers the sub-topics (all named in the rationale as present) but at shallower
depth than the reference. This is a "quantity of evidence" problem — 2 searches per
subagent call gives overview-level coverage; 3 searches gives more specificity.

Concrete gaps:
- drb_en_60: "target characterization/ID techniques" — needs more depth on how to
  identify and characterize cislunar objects (RCS, photometric signatures, etc.)
- drb_en_100: "granular typology" (Table 1 in reference) and "ethical discussion"
  (consent, regulation). The current prompt doesn't push for ethical depth specifically.

Pattern: In R7 (when drb_en_60 scored 5.0), the subagent likely made 3 searches
on characterization. In R8/R10, it defaults to 2 searches, missing specifics.
Similarly, drb_en_100 needs one more search on ethics/typology to match reference.

## Candidate lever

**Default subagent to 3 searches** — currently "2-3 times" causes model to default
to 2. Changing to "3 times (use 2 only if topic is very narrow)" pushes toward 3
searches per subagent call, which adds ~50% more evidence per call.

This is safer than Round 5's approach (which forced the MAIN agent to call 3 subagents,
causing poor-quality third calls). The subagent has a well-defined topic scope from
the main agent — it just needs to search it more thoroughly.

Expected outcome:
- More searches on characterization/ID for drb_en_60 → COMP 4→5
- More searches on typology and ethics for drb_en_100 → COMP 4→5
- DEPTH follows COMP: deeper evidence = deeper synthesis

## Specific change

`_subagent_prompt` step 1: "Call `tavily_search` 3 times using DIFFERENT search angles
(you may use 2 if the topic is very narrow and 2 searches clearly cover it fully)."

## Success criteria
- RACE > 4.85 (beats 4.80 by >0.05 → "improved").
- Both drb_en_60 and drb_en_100 RACE ≥ 4.75.
