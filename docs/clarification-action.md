# P3.1 bounded clarification action

Issue #39; accepted design #37 / PR #38. Implementation baseline:
`a4bad1a8742a97021502e71208bd7162c6b37c44`. This admission is frozen before
production implementation. Development examples are exposed/design-seen, not
the reserved fresh P3 panel. No live request is authorized.

## Semantic admission

Extend the existing recipe entry, not P1 or a second planner. One shared message
and JSON-schema-constrained completion produces one strict action:
unchanged `request`, unchanged `declined`, or
`{"outcome":"clarify","clarification":{"kind":...,"choices":[...]}}`.
The enclosing action contract becomes `recipe-request-json-v2`; native recipe
versions/shapes remain 0.1. No model-authored presentation is admitted.

Every choice has exactly `id` and `semantic_value`. IDs are case-sensitive local
ASCII identifiers matching `[A-Za-z][A-Za-z0-9_-]{0,31}`, unique within the
clarification. There are 2-4 distinct semantic alternatives, not selections of
several analytical requirements. Unknown fields/types, ranking, recommendations,
SQL/formula/task fields and arbitrary semantic JSON reject.

| Kind / semantic type | Exact semantic value fields | Cross-choice invariant |
| --- | --- | --- |
| `count_basis` | `type`, `scope` (native OverviewRequest), `value` | Same explicit Overview scope; distinct values from booked_seats, known_booking_accounts, attendance_visits, distinct_people; must include booked_seats |
| `comparison_roles` | `type`, `request` (native CompareRequest) | Exactly two orientations of the same two distinct explicit full months; one is the exact role reversal of the other |
| `center` | `type`, `request` (native OverviewRequest) | Same month/timezone; distinct explicitly supplied center codes |
| `metric_meaning` | `type`, `scope` (native OverviewRequest), `value` | Same explicit Overview scope; distinct values from confirmed_booked_amount, cash_received, posted_refunds, profit; must include confirmed_booked_amount |

`scope` preserves the already bound center/month, not a custom filter object.
All native dates/timezones/metrics/center constraints use existing validators.
Equivalent instants identify the same semantic alternative. Comparison scope
is all-center booked amount; multi-month aggregation is not admitted.
Center choices and Overview scopes must echo code literals from the question,
without a name/alias lookup or normalization. Literal presence does not prove
entity existence or the user's intended scope. No DB is opened to validate it.

Only booked seats and booked amount are supported alternatives within these
Overview clarifications. Other count/amount meanings are explicitly labeled
not available through the recipe entry; known booking accounts remain supported
separately in P1. No fallback, executable new metric or selected choice occurs.
Their enum meanings come from the reviewed distinctions, not arbitrary strings.

The model must use the explicit supplied scope/periods. Type/calendar validation
and cross-choice consistency cannot certify natural-language intent or that a
period was correctly extracted. That remains a P3 evaluation obligation, not a
new heuristic date parser, hidden default or claim of grounding. `time_scope`,
missing-year/baseline/k collection, multiple ambiguities, dynamic lookup, names,
arbitrary metrics/dimensions and multi-select remain unimplemented. A current
decline on deferred ambiguity is not automatically a necessary refusal.

## Pure types and presentation

`grepbit.clarification` supplies immutable typed values, `SemanticChoice` and
`Clarification`, with strict mapping admission and fixed `KernelError` failures.
No raw model mapping is retained. Choice IDs reference authoritative values;
no binding token, resume endpoint, state store or execution helper is added.

`grepbit.presentation` supplies one immutable `ClarificationPresentation` with
exactly `text` and `blocks` on the wire. It contains exactly one `ChoicesBlock`:
`type=choices`, `selection=single`, and 2-4 options containing `choice_id`/`label`.
Text/labels are nonempty valid UTF-8 bounded to 256 bytes. Construction/mapping
admission requires the semantic clarification and validates all IDs exactly
once, with no missing/unknown/duplicate reference. Reordering or relabeling
presentation cannot change the immutable semantic choices.

`render_clarification` uses fixed English templates and validated typed values.
English-only rendering is an explicit initial limitation; question-language
detection, an i18n framework, a second text-generation call and model-supplied
labels are not added. This is a plain-text/data contract, not executable markup.
No table/chart/generic block, nested UI AST or arbitrary data payload exists.
Future types/localization need separate admission; presentation is not a
replacement for the strict semantic action schema.

## Adapter and evidence

`RecipeInterpretation` retains its existing proposal/pack/error/evidence fields
and adds optional semantic clarification and presentation. A valid clarify
action has neither error nor proposal/pack; request validation passes and
kernel execution stays `not_run`. All native/scalar/grouped entry points and
SQLite connection creation must remain untouched. There is one fake/live
transport attempt at most and no retry, lookup, snapshot or second turn.
Existing decline error/outcome behavior and answer dispatch stay intact.

The same privacy-safe export records semantic clarification and deterministic
presentation separately, with explicit `model_outcome=clarify`. Deadline and
privacy failures must not return an actionable clarification/presentation.
Schema/context/instruction/generation identities change deliberately, not P1
or native recipe identities. Existing byte limits remain unchanged.

The historical P2 runner remains an answer-only regression panel, not a P3
evaluator. An unexpected clarify is a `wrong_request` there, with failed request
grading and separate clarify evidence, not refusal or operational success.
Historical outcome records are never rewritten. New module hashes are pinned
by the recipe manifest path; old accepted manifests remain immutable/ineligible
for the changed source. No new formal panel or accepted live manifest is prepared.

## Required offline evidence

Pure constructor/mapping bounds and invalid-type matrices; role reversal and
fixed-scope consistency; presentation references, reorder/localization and
single-selection checks; one-shot fake transport with every DB/native entry
poisoned on clarify/decline; strict JSON/diagnostic/privacy/deadline regressions;
all original P1/P2 checks; actual P1 wire equality; old/new schema and message/
request byte accounting; source/gold/history preservation.

Passing these establishes wiring and admission, not correct live clarification,
fresh generalization, resume, synthesis, product routing or P3 completion.

## Identity and size impact

The recipe context, instruction, output contract and structured-output identities
advance from v1 to v2 **only to admit the clarification action and its bounded
meanings**. The schema name remains `grepbit_recipe_request`. Existing request/
decline schema branches and the three runtime recipe-meaning entries are
byte/canonical-value identical to the accepted baseline. The instruction changes
the ambiguity policy and adds clarification rules; it does not retune answer
semantics. The catalog hash is unchanged.

Canonical SHA-256 identities:

| Identity | Accepted v1 | P3.1 v2 |
| --- | --- | --- |
| Action schema | `ac6ca4d71fbe6a69c978231458bc6d4be7fca3f5ebbee732d4cdedad0dec9a02` | `a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00` |
| Context | `7de6ed524fa5ddaeb530038c3a7b127461a7edb557749b61ef28558d359d6b87` | `1cae4d1955ab76ed2205b5b22fc85a33fabaa3274dca618af5cd4cade656d151` |
| Instruction | `cbf9e613e6b2a8e42ff758f9b0ceed1d2b4227be1a4d5d17cea1aee62b1cb270` | `8fbfa08c428220d452b7f83ccea7c908fdc2349641510bd8911d0055fa35acf5` |
| System message | `5893fb44fbad47c3e5b2f970e0165d0caaf062e75ac9af88dc80e6dcd4a2ffab` | `911ebd780de32eadc535c2b52f55c3c013a7ca809f3c5905f9c0913dcebfc3cb` |
| Response-format wrapper | `4333d65dede04246311681767015be7438503ff019b239d1d0c0194ab9a037ab` | `4f4e3ea6ec8ba6951d353d15c6388633f7c687ae0d19bb5925e80047dbc7fc86` |

UTF-8 measurements use the same pre-implementation synthetic witness question
and actual fake-transport request serialization, not a token estimate:

| Surface | Before bytes | After bytes | Delta |
| --- | ---: | ---: | ---: |
| Canonical schema | 2,889 | 7,875 | +4,986 |
| Canonical context | 5,792 | 11,693 | +5,901 |
| Instruction | 2,233 | 3,453 | +1,220 |
| Complete system message | 8,026 | 15,147 | +7,121 |
| Serialized recipe request | 12,072 | 25,250 | +13,178 |

Native request shapes are reused in semantic values instead of introducing a
second period/filter grammar. This repeats those shapes in the expanded schema;
the existing route sends that schema both in context and in `response_format`.
The resulting request is about 2.09 times the old size. This is a real cost,
not evidence of improved efficiency. Tokens, model latency and provider schema
compatibility remain unknown without a separately authorized run.

Limits remain question 4,096 bytes, complete request 32,768 bytes, response
131,072 bytes, 2,048 output tokens and one 60-second call. A 4,096-byte ordinary
ASCII question fits; a 4,096-byte all-quote question does not after JSON escaping
and fails `input_too_large` **before HTTP**. Individual caps are not a promise
that every combination fits the total cap; it is not silently raised.

**P1:** source/protocol untouched. Actual before/after request bytes match:
2,902 bytes, SHA-256
`bd657d31b50a6cc19bdad954b0ad30f6772a05b0aba36ade880d860f7629e53a`.
There is no `response_format` or clarify in P1. Its existing independent wire
and identity regressions also remain mandatory.

**P2:** request/decline schema, recipe meanings, native execution, fixture,
frozen panel and expected facts remain protected. The shared recipe model wire
has deliberately changed, so the accepted v1 9/9 live result is not live
validation of v2. Existing test pins retain historical v1 identities alongside
explicit v2 identities; no oracle, gold or old manifest is repinned.

## System impact and acceptance limits

- **Product scope:** four closed ambiguity kinds and one `choices(single)` block;
  zero new analytical operators, metrics, recipes, SQL paths or repairs.
  The admission is not missing-field collection, grounding or a planner loop.
- **Complexity:** two small pure modules, changes to the existing recipe adapter,
  and one compatibility branch in its evaluator. No dependencies, configuration
  keys, route, service, registry, state store or localization framework is added.
  Maintenance includes four semantic variants, cross-choice invariants and
  templates, plus the larger shared schema/prompt.
- **Safety/evidence:** fake transport and poisoned execution entry points protect
  zero analytics. Strict parsing, structured-output enforcement, privacy and late
  deadlines remain fail-closed. Caller-supplied string-like mutable objects are
  rejected by explicit type guards rather than equality-only enum checks.
  Returned error objects are fresh fixed errors; this does not claim every
  intermediate Python exception lacks an internal context.
- **Generalization/portability:** these are exposed development regressions.
  Shape checks and code-literal presence do not prove intent, period grounding,
  ambiguity necessity or source existence. Presentation is English-only plain
  text. No PostgreSQL parity, private-source confirmation or new product-entry
  routing is inferred.
- **Acceptance:** offline implementation is a candidate for independent owner
  review, not self-certified acceptance. No fresh P3 families, evaluator,
  44-input panel, resume, synthesis or live manifest was authored. No live model
  request is authorized. Process-transfer/RSI improvement is not demonstrated;
  active human effort and comparable end-to-end elapsed time were not measured.

## Offline candidate validation

Source: branch `feat/p31-clarification-action`, accepted baseline above plus the
reviewable uncommitted diff. No commit, push, merge or issue closure has been
performed for this slice. Evidence is exclusively created under
`.artifacts/p31-offline-weGvi9/`; it is local/ignored, not a new acceptance tracker.
Production impact: three files, +439/-32 lines (two new pure modules and the
existing adapter). The evaluator adds three lines for clarify compatibility.
No native executor, shared gateway, P1 adapter, fixture, translation or gold
file changes. The original 107 P0/P1.1 methods/files remain protected.

Commands actually run with the existing pinned Python 3.11.13 / SQLite 3.50.4:

```bash
.artifacts/p12-XW5dPo/venv/bin/python -m unittest discover -s tests -p 'test_recipe_clarification.py' -v
PYTHONPATH=tests .artifacts/p12-XW5dPo/venv/bin/python -m unittest test_recipe_model test_recipe_clarification test_json_diagnostics test_structured_output test_recipe_smoke -v
PYTHONPATH=tests .artifacts/p12-XW5dPo/venv/bin/python -m unittest test_clarification test_presentation test_recipe_clarification test_recipe_smoke.RecipeSmokeTests.test_unnecessary_clarification_is_persisted_as_wrong_request_without_execution -v
.artifacts/p12-XW5dPo/venv/bin/python -m unittest discover -s tests -v
.artifacts/p12-XW5dPo/venv/bin/python tools/fixture.py build --db .artifacts/p31-offline-weGvi9/fixture/learningops.sqlite
.artifacts/p12-XW5dPo/venv/bin/python tools/fixture.py check --db .artifacts/p31-offline-weGvi9/fixture/learningops.sqlite --report .artifacts/p31-offline-weGvi9/fixture/report.json
git diff --check
```

The successive targeted runs passed 14, 103 and 51 methods. The complete run
passed **594/594**, with no skipped/expected-failure methods, in 62.018 seconds:

| Suite | Passing methods |
| --- | ---: |
| P0 fixture/language assets | 21 |
| P1.1 kernel/CLI/review witnesses | 86 |
| P1.2 model/gateway/envelope/logging/runner | 169 |
| P2 deterministic recipes/grouping/composition | 178 |
| Recipe adapter/diagnostics/structured output/runner, including one new compatibility method | 90 |
| P3.1 pure models/presentation/new adapter checks | 50 |

There are 51 added methods, including the compatibility method above. All frozen
P2 nine-input meanings still execute and grade correctly with fake completions;
this is not a model evaluation. The fresh P0 fixture check passed 18 reference-SQL
and nine mechanism checks. Its 12 behavioral cases remain `not_implemented`.
The before/after wire probe also verified all 242 prior artifact hashes unchanged.

No failing unittest run was discarded. A static review found and corrected
mutable string-like enum admission before its regression tests ran. The first
wire-measurement script used the wrong evidence key (`context` instead of
`runtime_context`); that tooling error and second successful measurement are
recorded in `protocol-measurements.json`. Neither changed expectations, recipe
semantics or evidence. Full logs and protocol measurements remain in the evidence
directory; source/diff identity accompanies the final handoff.

**LIVE MODEL ATTEMPTS = 0.**
