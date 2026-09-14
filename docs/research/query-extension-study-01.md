# Query families: compiler feasibility is not planner readiness

2026-09-14. **Research implementation complete; no production promotion.**
Follow-up: [question-encoding diagnostic](query-extension-encoding-01.md)
isolates a harness input-format contribution and recovers all four original
questions twice. The observations below remain historical results, not the
latest estimate of natural-question planner readiness.
Scope/ruler: [query-extension-study](../plan/query-extension-study.md).
Durable per-case outcomes, report hashes and validation counts:
[`summary.json`](../../evidence/query-extension-study/summary.json).
Detailed synthetic/private runs: `.artifacts/query-extensions-20260914/`.

## Implemented, isolated from serving

- `domain/query_extension_study.py`: closed rows/aggregate/combine contracts;
  production QueryPlan still rejects these wrappers.
- `adapters/sqlglot/query_extension_study.py`: visible row projections,
  standard SQL unit conversion, independently aggregated components joined by
  entity identity, and optional maximum/minimum selection. Reuses compiler
  predicates, parent joins, visibility, segments and SQL policy. No raw model
  SQL, arbitrary formulas or new agent framework.
- `evals/query_extension_study.py`: serial synthetic-only planner/oracle runner
  and replay; handwritten SQL oracles execute before model calls.
- `evals/fixtures/query_extension_units.json`: research-only source-unit
  bindings, not a newly approved production overlay format.
- 44 new contract/value checks, including ten random count instances.

Rows support base-table columns, stable PK ordering and explicit LIMIT
disclosure. Parent-label projection and paging are outside this prototype.
Conversion supports C/F AVG/MIN/MAX and minutes/hours SUM/AVG/MIN/MAX,
preserves NULL and does not round. Temperature SUM, incompatible/unbound units,
converted HAVING and ratio/share/growth combinations refuse. Input thresholds
in other units are not a supported conversion feature. Source units are trusted
metadata; a model-selected target or null conversion still does not prove intent.

Combine starts from the full filtered entity population, uses a single-column
PK (not a label), keeps component windows/bindings separate, fills only missing
child counts with zero, and preserves NULL SUM/AVG. All non-NULL extrema ties
remain, including a winner with no temperature. This is a disclosed study tie
convention, not a new production default. Compiler instances are request-local.

This separate path does NOT claim production gate, name-grounding, lifecycle,
MCP identity, total-deadline or full disclosure/lineage parity. It remains
`unverified_semantics`. Visibility is configuration-based, not automatic PII
classification. Results above 200 rows are not scored by the research runner.

## Live results

Gemma 4 31B, temperature 0, thinking off, serial calls. Existing on-prem gateway
and grepbit_ro, synthetic IoT/Service only, sample limit 0; no rows sent to the
model and no DB mutations. **95 actual model calls**, under the self-imposed
96-call bound. No repairs or transport retries were observed in the baseline;
research arms use no repair turns or SDK retries. Endpoint load/session state
was not controlled, so no causal batching or latency conclusion is justified.

### Explicit authored panel: 19 answerable + 2 unanswerable

| Arm | Exact answers | Accepted extra output, manual | Wrong answers | Refusal on answerable | Necessary refusal | Invalid/failed |
|---|---:|---:|---:|---:|---:|---:|
| Production v15 baseline | 4 | 1 | 1 | 11 | 2 | 2 |
| Research wire v1 | 14 | 0 | 2 | 0 | 2 | 3 |
| Research wire v2 | 18 | 0 | 1 | 0 | 2 | 0 |

The baseline extra-output case correctly lists offline device IDs/models with
COUNT=1 per device PK; this is separately reviewed, not silently pooled into
exact-reference scores. Its wrong answer is average hours returned as 55.4444
minutes under an hours alias, rather than 0.9241 hours. `answered` and column
labels are not value checks. Baseline plan objects were saved as representations,
not JSON plans: the artifact supports statuses/values but not direct plan replay.

Wire v2 narrows displayed component properties to the accepted contract and
requires an explicit conversion object or null. Compiler semantics and oracles
stay unchanged; no question-specific examples or vocabulary exceptions were
added. These two wire changes are one combined intervention, not independently
measured causes. The remaining wrong answer requests counts per ticket but
returns work-log/ticket counts per team, omitting events. V1 made a similar
misread plus an invalid dimensions field: fixing that shape made the semantic
error executable. Better schema compliance is not automatically safer.

### Original four + eight nearby natural-wording probes

Frozen before this run: Japanese, independent July/August windows, natural-key
multi-hop joins, a parent-label row query outside scope and a missing rental
definition. Predeclared SQL alternatives compare complete results, not arbitrary
projections (e.g. site ID versus label, or an independently checked extra label).

| Arm, 12 cases | Matching answers | Wrong values/scope | Unjustified answer to unanswerable | Refusal on answerable | Invalid/failed |
|---|---:|---:|---:|---:|---:|
| Wire v2 | 4 | 6 | 1 | 0 | 1 |
| Same content, question serialized last | 5 | 5 | 1 | 1 | 0 |

Both layouts answer only **1 of the original 4** correctly: temperature at the
highest-alert site. Other failures change devices to sites, omit Fahrenheit
and add a top-one limit, count work logs instead of projects, add daily grouping
to a total, or ignore rental scope. These are not rounding/alias-only issues.
Question placement rescued the short hours-total probe but did not fix the
three original failures. Earlier artifacts remain unchanged; the later evaluator
separates typed compiler refusal from malformed output. Neither layout proves
a model-internal attention or endpoint mechanism.

### Diagnostics, never pooled into model accuracy

- Correct plans selected from the explicit-question run and injected for the
  original four: **4/4 PostgreSQL/reference agreements, zero model calls**.
  This proves bounded computation feasibility, not automatic intent.
- Researcher supplies the correct operator kind and removes other kinds and
  unreachable schema definitions: **2/8 agreements, 5 wrong, 1 invalid**.
  Original device details and the team/project/ticket probe improve; the
  previously successful ranking probe becomes invalid. None of the conversion
  probes match. Operator restriction has local value, not a universal fix;
  product routing would still need to obtain the supplied information.
- The first operator-script attempt failed on import before DB/model activity;
  it was corrected and is not counted as a model failure or call.

## Conclusion and next slice

The four requests are computable as one SQL SELECT using a small typed
extension. Live explicit-question gains show the model can use it, not merely
that researcher-written plans work. But original/natural questions still choose
wrong entities, populations, grouping and units. The new operators do not
supply independent evidence that those choices match intent.

**Do not promote the combined automatic planner to Web/MCP.** Preserve the
prototype/regression assets, leave production QueryPlan and prompt v15 unchanged,
and do not add keyword exceptions or a same-model intent certification gate.
Next isolate entity/population, grouping and target-unit selection on this
panel; compare reviewed metadata and operator-specific interfaces with both
lost-requirement and unwanted-addition controls. Assisted routing/identifiers
must remain diagnostic, not product accuracy. Promote one end-to-end slice only
after repeated original-question and old-control measurements support it, then
test integration with existing grounding, visibility, evidence and lifecycle.

These are authored/seen development cases, not unseen-user generalization or
full differential closure of the extended algebra. No historical score changed.
Full validation: **1,948 offline tests, 0 skipped; static passed**. New checks
cover hidden columns/unit metadata, parameter isolation, segments, independent
windows, four child-activity populations, asymmetric counts, ties, NULL winners,
golden conversions and duplicate-preserving evaluation.
