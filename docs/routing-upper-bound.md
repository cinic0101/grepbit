# Routing upper bound (#79)

Contract `routing-upper-bound-v1`. It is step 3 of the owner-delegated
sequence
([#79 #issuecomment-5903014322](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903014322)).
It measures what a perfect router could gain, before anyone builds one. Each
dev-panel input is routed, by a fixed table, to a context narrowed to its
analysis type. The model's answer then goes through the unchanged production
validation, kernel and grader. The current candidate on `dev` does not change.
The experiment is observational: it is never a candidate, a run-index entry,
a gate verdict or promotion evidence.

## Question

31B's failures on the dev panels all sit at the answer/clarify/decline
boundary. Across 692 recorded 31B dev rows, the recipe layer never failed
where it was assessed; it is assessed only on answers. The
one system context serves three recipes and four clarification kinds, and a
count-only change (v9, v11) moved Compare decisions. If each input saw only
the recipe and clarification kinds of its own analysis type, would the
boundary decisions improve without breaking others? If a perfect router gains
nothing, a real router cannot, and no router is built.

## Scenarios and the router table

The scenario of an input is its analysis type, derived from existing accepted
oracles:
- an answer oracle gives its `recipe_id`;
- a clarify oracle gives its kind's recipe: `count_basis`, `center` and
  `metric_meaning` are `overview`, and `comparison_roles` is `compare`;
- a decline oracle has no recipe. Its scenario comes from the table below,
  which the ruler pins.

| Panel | Families routed to `overview` | Families routed to `compare` |
| --- | --- | --- |
| `p3-dev-bound-meaning-v1` | `dev-BM5`, `dev-BM6`, `dev-BM7`, `dev-BM8` (decline, by the table) | `E02_compare`, `dev-BM2`, `dev-BM3`, `dev-BM4` |
| `p3-dev-mechanism-probe-v1` | `dev-BM6`, `dev-MN1`, `dev-MN2`, `dev-MN3` | `E02_compare`, `dev-MC1`–`dev-MC5`, `dev-A3`, `dev-BM2`, `dev-MY1`, `dev-MY2` |

`dev-BM8` asks for the Overview plus a deduplicated count of people. Its
supported part is an Overview, so the table routes it to `overview`. Every
other family's scenario follows from its oracles, and the ruler checks that
the table agrees with them. The table is experiment configuration, not an
oracle: it changes no expected result.

## Narrowed context

For scenario `S`, the runtime context is `recipe_model.runtime_context()` with
three changes and no other:
- `recipes` keeps only the entry whose `id` is `S`;
- `clarification` keeps the kinds whose recipe is `S`, plus `boundary`;
- `output_schema` keeps only the `oneOf` branches that `S` can produce:
  - the request branch whose `recipe_id` is `S`;
  - the `declined` branch;
  - the `clarify` branch, with its kinds filtered to those of `S`, and dropped
    if none remain.

  Every kept branch is byte-identical, in canonical JSON, to a branch of the
  production schema.

The system message is `SYSTEM_INSTRUCTION + "\n" + canonical_json(narrowed
context)`, built by `recipe_model._messages`. The user message is the
question. The structured output is the narrowed schema, under the schema name
`grepbit_recipe_request_<S>`, sent through the route's client as a JSON-schema
constraint. `SYSTEM_INSTRUCTION` and every unlisted context field are
unchanged, so only the context narrowing varies.

The route is `litellm-gemma-4-31b` only. The Bedrock route pins and compacts
only the production recipe schema, and a narrowed schema would need its own
grammar-size check there; that is out of scope for v1.

## Grading

The content the model returned goes through
`recipe_model.interpret_recipe_and_execute`, using the same replay client as
`tools/evaluate.py --replay`: the production validators, kernel execution and
presentation run unchanged, with zero further model calls. `p3_grading.grade`
then grades the result against the panel oracle. A response that is not valid
JSON, or that the validators reject, is the model's own content: it is graded
`invalid_output` and counts as wrong. The narrowed schema is a subset of the
production schema, so a reply valid under it is also valid under production.

## Comparison with the current candidate

The comparison reuses the candidate gate's rules (`docs/candidate-gate.md`):
- **Baseline classes** are the aggregate classes of every indexed run with the
  current candidate's bytes on the panel and route.
- **Sentinel.** At least one baseline run must be complete and recorded under
  the experiment's authorization reference.
- **Per-input class:** `fixed`, `broke`, `unchanged_correct`,
  `unchanged_wrong`, `excluded` or `unassessed`, as in the gate.
  - A fix needs an assessed sentinel row on that input.
  - A route failure is unassessed, never a break.
- **Verdict** per panel and overall, first match: `regression` >
  `inconclusive` > `passed` > `no_fix`.
- The report states the verdict as a development observation of a
  hypothetical router, not a candidate verdict.

## Authorization, slot, stops and output

These are the same as the reading diagnostic (`docs/reading-diagnostic.md`).
- **Packet:** the canonical evaluation packet is embedded. The packet pins
  the router table, each scenario's narrowed context digest, schema digest and
  messages digest per input, and the run budget (`inputs × call timeout +
  120` s).
- **Envelope:** `routing-upper-bound-authorization-v1`, with a grant URL and
  one new `.artifacts/` slot, written with exclusive create.
- **Live:** one call per input, no retry. It refuses before any send if the
  source changed.
- **Stops:** `timeout_streak`, `network_streak`, `budget`, `anomaly` (any
  route, configuration or envelope failure) and `interrupted`. Model-content
  errors are graded and never stop the run.
- **Persisted per input:**
  - `case_id`, `family_id`, `question_sha256` and `scenario`;
  - `state`: `not_started`, `reserved`, `returned` or `failed`;
  - `attempt`, `http_attempts`, `elapsed_seconds` and `error_code`;
  - `validated_action`: canonical JSON, exactly as evaluation v2 keeps it;
  - `graded`: the `p3_grading.grade` result, or null.

  No raw completion or reasoning is kept.
- **Row states.** A reply that reached the pipeline is `returned` and
  graded, even when it is malformed (`invalid_output`). A route,
  configuration or envelope failure is `failed`, with its `error_code` and no
  grade.
- **Readback** recomputes the comparison from the run index and adds it to the
  report as `comparison`:
  - `baseline_runs` and `sentinel_runs`;
  - `inputs`: `case_id`, `scenario`, `baseline_class`, `sentinel_assessed`,
    `experiment` (`correct`, `wrong` or `unassessed`), the graded `outcome`
    and the `class`;
  - the case-id lists `fixed`, `broke`, `excluded` and `unassessed`;
  - `counts`, `verdict` and `refusal`.
- **Comparison refusal.** When no baseline run under the report's authorization
  is complete, the comparison has `verdict` null and `refusal` `no_sentinel`
  (none recorded) or `sentinel_incomplete`. The report still reads back.
- **Preparation refusals**, each `invalid_manifest` with one closed reason:
  - `not_dev_panel`: the panel is not `dev`-tier;
  - `route`: the route is not a LiteLLM route;
  - `router_table`: the table has no entry for the panel, lacks a family, or
    disagrees with an oracle-derived scenario.

```
.venv/bin/python tools/evaluate.py --routing-upper-bound --prepare --panel <dev panel> \
    --route litellm-gemma-4-31b --db <db> --accepted-commit <sha> --output <new dir>/packet.json
.venv/bin/python tools/evaluate.py --routing-upper-bound --bind-authorization --packet <packet.json> \
    --owner-authorization-reference <grant URL> --output <dir>/authorization.json --run-output-dir <slot>
.venv/bin/python tools/evaluate.py --routing-upper-bound --live --packet <packet.json> \
    --authorization <authorization.json> --db <db> --accepted-commit <sha> --env-file <env file> --output-dir <slot>
.venv/bin/python tools/evaluate.py --routing-upper-bound --report --report-path <slot>/report.json
```

## Claims and limits

- **It is an upper bound for this design only.** The router here is a fixed
  table derived from oracles; a real router makes errors of its own. A
  `passed` verdict shows that narrowing can help on these inputs, and bounds
  what a router could add. It does not show that a router would reach it.
- **Narrowing is the only variable.** `SYSTEM_INSTRUCTION`, including its
  count and decline text, is unchanged. The experiment neither resolves nor
  tests the count specification's tension between "people counts"
  unsupported and `count_basis` clarification.
- It covers one route, one run per input, and development inputs only.
