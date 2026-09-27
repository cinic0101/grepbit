# Coverage matrix (#87 step 3)

Status: approved by the owner on 2026-09-27 (recorded on #87). The dev-tier
panel `p3-dev-matrix-v1` (`evals/dev/`, built by `tools/build_dev_panel.py`)
fills every row below except the two deferred ones (D5, D10) in all three
languages; the golden tier follows the fill rules at the end.

The golden tier is filled cell by cell against this matrix, so "common and
generalizable" is checkable rather than felt. Cells are product boundaries of
the three V3 recipes (Overview, Compare, Breakdown), the four typed
clarification kinds and the decline categories; they are not benchmark
questions. Public BI question-type taxonomies (descriptive aggregate,
period-over-period comparison, composition/share, ranking/top-k, filtering by
entity, time scoping, ambiguity, out-of-scope) were used to name the rows,
not to copy questions.

## Rows: analytical intent

| Row | Intent | Expected branch | Recipe / kind |
| --- | --- | --- | --- |
| A1 | One center, one month, the three core metrics | answer | Overview |
| A2 | Overview with explicit definitions that match the reviewed meanings | answer | Overview |
| A3 | Compare two named months, orientation bound by grammar | answer | Compare |
| A4 | Compare with one stated year shared by both months, non-adjacent months | answer | Compare |
| A5 | Top-k courses by amount with explicit k and month | answer | Breakdown |
| A6 | Share of the whole for the top-k subtotal, explicit k | answer | Breakdown |
| C1 | Count meaning open (seats vs accounts vs visits vs people) | clarify | count_basis |
| C2 | Two months named with no orientation | clarify | comparison_roles |
| C3 | Two to four center codes named for one Overview month | clarify | center |
| C4 | Amount meaning open (booked vs cash vs refunds vs profit) | clarify | metric_meaning |
| D1 | Explicit profit, cost, target attainment or a causal "why" | decline | D01 |
| D2 | Cash received, refunds or historical booking state at a past point | decline | D02 |
| D3 | Annual, multi-month or partial-month aggregation | decline | D03 |
| D4 | Supported outputs plus an unrelated or unsupported requirement in the same request | decline | D04 |
| D5 | Missing year, month, baseline or k with nothing in the text to recover it | decline | D05 (deferred: the evaluator scores D05 as not eligible, so no dev family yet) |
| D6 | Unsupported filter, population, grain or dimension (daily, per instructor, per region) | decline | D06 |
| D7 | Arbitrary formula or unit/currency conversion | decline | D06 (the oracle parser admits D01-D06 only) |
| D8 | Supported overview plus an explicitly required attendance count | decline | D04 |
| D9 | Enumeration of members or arbitrary row details | decline | D06 |
| D10 | Center referred to by name, not code | deferred | C05: name-only references are deferred grounding/clarification and the contract says a decline here is not success; no dev family until grounding exists |

## Columns: surface variation

| Column | Values |
| --- | --- |
| Language | zh-TW, en, ja (every cell in all three) |
| Register | formal, colloquial |
| Time phrasing | explicit month with year; explicit month with the year stated once for two months; relative phrase ("last month") is a D05 deferred case, not scored as a correct decline |
| Entity phrasing | exact code; code with different casing (must echo exactly); name (deferred grounding, not scored) |
| Noise | none; one irrelevant sentence before the question |

## Fill rules

- Dev tier: the agent fills every row in every language first; unlimited runs.
- Golden tier: independent author sessions fill each row with at least one
  family per register and one per time phrasing where the row admits it; an
  independent reviewer recomputes answer facts by SQL over the fixture and
  checks clarify and decline oracles against the contracts; the owner
  ratifies realism; families are frozen with exposure labels.
- A cell is "covered" when at least one golden family passes on the primary
  route and the family has never been changed to fit a candidate.
- New problems found later go to the dev tier first; a golden addition needs
  the independent review and a new panel version.

## Not in the matrix (deliberately)

Resume after clarification, presentation text, multi-turn state, real-data
transfer (P5) and anything that requires a clock or AS_OF default.

## Dev panel `p3-dev-matrix-v1`

| Family | Oracle | Center / months | Note |
| --- | --- | --- | --- |
| dev-A1 | overview | CTR-A01, 2026-03 | plain overview |
| dev-A2 | overview | CTR-B01, 2026-03 | explicit reviewed definitions in the question |
| dev-A3 | compare | 2026-03 vs 2026-02 | orientation bound by grammar in all three languages |
| dev-A4 | compare | 2026-04 vs 2026-02 | non-adjacent months, one stated year in every language, negative growth |
| dev-A5 | breakdown k=3 | 2026-03 | all three observed courses, share 1/1 |
| dev-A6 | breakdown k=2 | 2026-03 | share 64/79 |
| dev-C1 | count_basis | CTR-B01 | "how many people", naming seats vs booking accounts as the open alternatives |
| dev-C2 | comparison_roles | 2026-02, 2026-03 | two months, no orientation |
| dev-C3 | center | CTR-A01 or CTR-A02 | two codes, one month |
| dev-C4 | metric_meaning | CTR-A02 | "revenue" |
| dev-D1..D9 (no D5, no D10) | decline D01/D02/D03/D04/D06/D06/D04/D06 | | see the row table |

Answer oracle values are produced by executing the native request through the
kernel against the synthetic fixture (`tools/build_dev_panel.py`), and a
scripted-response mock run grades all 54 cases correct. Authoring is
`development`; families that paraphrase or translate an exposed development
family by paraphrase, translation or code/k substitution (A1, A3, A5, A6, C1,
C2, C3, C4, D1, D2) keep the `exposed_regression` label and name their parent;
the rest (A2, A4, D3, D4, D6, D7, D8, D9) are `design_seen`. This panel is for iteration and its
results are development observations, never fresh evidence.
