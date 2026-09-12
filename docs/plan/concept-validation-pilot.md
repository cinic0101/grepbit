# Concept validation: ruler checkpoint (2026-09-12)

Status: the authorized pilot is complete; **neither candidate is promoted**.
Two identical-prompt rounds, 162 Gemma requests, expose missing-meaning escapes
and ambiguity mishandling. See `../research/concept-validation-01.md` and
`evidence/concept-validation-01.json`. Final offline 484/static pass. Do not
expand the pilot or change production gates based on the earlier ruler pass.

## Outcome, ownership and authority

Measure separately whether a question requires a business concept and whether
a plan expresses that requirement. Do not replace either question with column
name overlap, or let model agreement certify natural-language correctness.

The user approved the preceding four-arm experiment with "ok 可以開始".
Earlier user instructions explicitly authorise necessary PostgreSQL and Gemma4
calls. These are permission references, not new permission granted by this file.
The root owns this coupled specification. Baseline is the existing dirty tree
at 746f168; preserve all earlier A5, period, grain and service work. No stage,
commit, push, dependency install, persistent DB write or production change.

The current AGENTS instruction requires a two-phase stop for a material
evaluation contract. This slice creates only rulers, fictional fixtures and
specification/evidence. Establish the existing behavior and intended evaluation
meaning, then stop before implementing a new grader or calling models. Existing
runtime contracts, historical scores and release gates do not change.

## Why this is not the old coverage audit

`docs/research/tier0-generalization.md`, section 2, records coverage audit v1
catching 1/2 drops with one false flag, and v2 catching 0/2 with no false flags;
added latency was 2-6 seconds. This is historical evidence, not a current Gemma
baseline. The existing adapter is a useful later comparator, not a proven gate.
It sees compiled interpretation and lineage. The proposed independent extractor
must not see those, the candidate plan, golden labels, expected answers or rows.

## Pilot ruler

`evals/cases/concepts/pilot.yaml` is 10 author-written families x zh/en/ja = 30
development questions. It is not a held-out generalization measurement. POS
probes use existing return definitions and explicit membership predicates;
service probes exercise an imperative homonym and missing business meaning.
Service has no positive reviewed refund definition: do not manufacture one.

The labels distinguish required, not_requested and ambiguous; an unavailable
binding is separate from whether the question requires the concept. Negative
membership/return predicates still express a concept, with inverse polarity.
Ambiguous families must not receive a forced binary expected plan. Labels are
author-proposed evaluation rulers, not newly owner-reviewed business defaults.
Review disagreement excludes a label from scoring until adjudicated, never
counts as model failure. Mentioning a concept to forbid filtering is not a
request to include that segment; eventually check the no-restriction requirement
too, rather than treating an empty concept list as evidence of a correct plan.

Mutation rulers use existing QueryPlan constructs only. Hand-computed fictional
instances prove that missing predicates, inverted NULL checks, dimension-only
mentions and numerator/denominator swaps change results. Include equivalent raw,
operand-filter and reviewed-metric forms, plus an accidental-agreement instance.
The reference evaluator and compiled SQL are checked against hand answers
separately. A clean compiler differential does not establish question intent.

Checkpoint tests characterize the existing gate rather than demand a production
replacement: green assertions pin both its false positive and its missed
semantic mutations. This is meaningful static/behavioral checkpoint evidence;
a red assertion demanding LLM-driven runtime bypass would misrepresent this
research-only scope. No missing imports, xfails or weakened goldens are evidence.

## Experiment after checkpoint authorization

Follow-up authorization: after the ruler results and explicit request to proceed
with this specification, the user replied "沒問題". The root now implements
and runs the bounded offline/shadow experiment below; this does not authorize
production integration. No other agent is writing this surface. The process-ID
preflight succeeded outside the sandbox and found no matching evaluation/test
processes. Initial source identity is the ruler manifest's dirty-tree digest.

Freeze the question set, labels, complete source hashes, model settings and
candidate plans before scoring. Do not use gold requirements as model input.

| Arm | Requirement extraction | Binding verification |
|---|---|---|
| A | Current lexical trigger | Current name-presence heuristic |
| B | Same lexical trigger | Bounded structural checker |
| C | Independent LLM, no plan/interpretation | Same checker as B |
| D | Direct LLM question-plus-plan audit | Explicit per-dimension rubric, Unknown allowed |

B receives only what the lexical baseline really infers: concept presence,
not a gold polarity or operand role. If those are needed but unknown, B must
report Unknown. Do not silently give B/C different gold information. Also run
the checker with gold requirements as an **oracle-input diagnostic**, never as
an end-to-end arm. This separates extraction errors from checker errors.

Start with the supported predicate forms in these rulers, using reviewed metric
expansion and existing plan structure. Unrecognised equivalence, conflicting
filters, segments, or scope cannot be certified: report Unknown. No universal
semantic IR, per-language exception table, new ontology or repair loop.

C returns only closed concept IDs, exact supporting question spans and supported
polarity/role, or Unknown. Validate IDs and literal spans mechanically, but do
not call span validation semantic proof. Ask for neither SQL nor reasoning
traces. D receives the same definitions plus the candidate QueryPlan, not rows,
gold labels, SQL or the planner's persuasive explanation. Wrong/malformed output
and transport failure stay separate from Unknown; do not turn them into passes.

Budget: initially 30 C calls plus at most 60 D calls on frozen correct/mutant
pairs, no automatic retries, temperature 0, thinking off, 20-second timeout per
call, at most 768 output tokens. At most two additional time-separated repeats
of this frozen pilot (270 total requested calls). Serial calls to the previously
authorised Gemma4 gateway using the ignored credential environment only. Outbound
data: synthetic questions, value-free schema, reviewed definitions and (D only)
synthetic candidate plans. No customer data, rows, secrets or endpoint URLs in
reports. No DB access is necessary for this pilot; later PostgreSQL checks use
grepbit_ro on localhost:5432, inline synthetic SELECTs and opaque DSN env names.

Pilot stop: no larger experiment if C offers no additional detection beyond A/B,
introduces a new known dangerous pass, or gets its apparent gain by refusing
most questions. Do not retune and rescore the same pilot as independent evidence.

If promising, expand to roughly 120 questions; split whole semantic families,
keeping translations together. Lock labels before candidate outputs, adjudicate
unclear labels with the owner, then add actual unseen owner questions separately.
Do not simultaneously change capability-rule selection or A5/A4 prompts.

## Measurements and integration stop

- Concept recall, spurious requirements, polarity/role errors and ambiguity
  handling, split by source/language/category. Report denominators explicitly.
- Dangerous semantic mutation pass rate, correct-control rejection/Unknown,
  and risk among accepted answers at comparable answer coverage. A missing
  definition is not the same as no requested concept. All-refusal cannot win.
- Planner/extractor joint misses on later live plans; an independent request
  context is not statistically independent evidence. The initial fixed-plan
  pilot cannot measure live-planner error correlation or answer improvement.
- p50/p95, token usage, calls, transport/format errors, and complete-run counts.
  Three time-separated observations are descriptive, not a proof of stability.

Even a positive pilot remains shadow-only. Neither model may override schema,
SQL, permission, PII or existing runtime concept gates. Production integration
or a refusal-policy change requires its own explicit checkpoint; any planner
prompt change gets a separate revision and affected-set regression. Evidence
that a new gate would clarify correctly is not evidence that answers improved.

Primary references researched in the preceding turn:
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://aclanthology.org/2025.naacl-long.228/
- https://aclanthology.org/2020.emnlp-main.29/
- https://arxiv.org/abs/2310.01798

## Checkpoint evidence

Complete; follow-up authorized above. Counts below remain the ruler-only results.

- `focused-01`: 47 passed. Includes 33 scalar plan/instance pairs checked
  independently through compiled SQL and the reference, two dimension-shape
  checks, eight legacy-gate characterizations, the three-language imperative
  control, coincidence control, pilot integrity and definition provenance.
- `static-01`: ruff check, format check and diff whitespace check passed.
- `offline-01`: 443 passed, no failures/errors/skips. Source hashes include the
  dirty pre-existing implementation; HEAD alone is not a reproducible snapshot.

Artifacts: `.artifacts/concept-ruler-20260912/`; durable manifest:
`evidence/concept-ruler-01.json`. These are synthetic offline results, not 30
live answers or a measured LLM gain. No production/runner implementation changed;
no model, PostgreSQL, credential access, install or Git write occurred.

The preflight process-list API was unavailable in this sandbox. This is not
evidence that there were no other processes. No shared model call or edit to
existing src/evals implementations was made; the scope remained new test and
specification artifacts. All validation commands started by this slice finished.
