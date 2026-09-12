# Concept obligations v2: ruler findings, not a model result

2026-09-12. Protocol and exact authority: `../plan/concept-obligations-v2.md`.
No v2 implementation, model requests, production change, or Git write.

## Result

The new ruler bank has 12 authored semantic families x zh/en/ja = 36 questions.
They are targeted development cases, not new generalization evidence. A
test-only payload schema can represent explicit unrestricted scopes, separate
grouping prohibitions, multiple scopes for one concept and partial unresolved
intent. This is representation coverage, not proof that a model extracts it.

All five previously recorded escapes still reproduce under unchanged v1. Three
additional authored checker probes expose implicit membership restrictions:
the no-request bypass allows both count(member_id) and count-distinct(member_id),
and a correctly supplied v1 numerator requirement still allows an implicitly
restricted denominator. These are not added to the frozen 51-pair scores.

## New failure: the deterministic checker can also miss the denominator

Question meaning: member transaction count / all transaction count.
Candidate plan: count(*) filtered by member_id not NULL in the numerator;
count(member_id), without an explicit filter, in the denominator.

The v1 checker returns pass (`predicate_binding_only`). It sees no denominator
predicate, but SQL's column count discards NULL input values. The plan therefore
returns 1 on both fictional instances instead of the intended 0.5 and 0.4.
The supplied numerator requirement is correct under v1; this example does not
need an LLM extraction failure to escape. It was found while designing the
new no-restriction rulers, not by a fresh model request.

Distinct-member count is another boundary: it selects only members but counts
unique members, not transactions. A qualifier-only pass may be legitimate while
the full answer is wrong. The new draft explicitly does not call a predicate
pass full-answer verification.

## New failure: the reference evaluator is wrong on nullable column counts

| Plan | Fictional instance | Hand / compiled DuckDB / PostgreSQL | Reference |
|---|---|---:|---:|
| count(member_id) | 4 rows, 2 member rows | 2 | 4 |
| count(member_id) | 5 rows, 2 member rows | 2 | 5 |
| member count / count(member_id) | 4 rows | 1 | 0.5 |
| member count / count(member_id) | 5 rows | 1 | 0.4 |

Cause: `evals/reference_eval.py::_aggregate` builds `present` but its count
branch returns `len(values)`. The SQL compiler counts non-NULL values correctly.
The [PostgreSQL specification](https://www.postgresql.org/docs/current/functions-aggregate.html)
agrees with the hand answers and both engines. This is not a choice of business
default or a new count definition.

The generator's raw count branch (`evals/plan_generator.py::draw_operand`) emits
only bare count, not nullable-column count. The separate property generator's
raw count branch does the same. This explains the missing direct form, not a
proof that no reviewed metric could ever expose it. Prior clean differentials
remain results for their recorded plans, not coverage of all count expressions.

One instance also intentionally makes two different denominator scopes agree
at 0.5; the other distinguishes them (0.5 vs 1/3). We need distinguishing
instances, not just a shared result on one convenient dataset.

## Executed validation and provenance

- Source baseline: 746f168 plus the prior dirty work. Executable/input digest
  before this slice: sha256:1a0f0052c4500f368079a3eeb647f00a6e6617bf2db0b869fea2c71ada071ce7.
- Source/input delta: new `evals/cases/concepts/obligations_v2_ruler.yaml` and
  `tests/contract/t0/test_concept_obligations_v2_ruler.py` only. No edit to v1
  checker, model driver, old cases, compiler, reference or generator.
- Final digest: sha256:fe44bc0822a7b0776b8edd77d1fd01d76a326cc10b65d26f98da60023971d7d9.
- Initial focused run: 117 tests, 113 passed, 4 reference failures; preceded
  formatting and the final implicit-denominator fixture label. This is discovery
  evidence, not final-source validation.
- Final static gate passes. Final full offline: 605 tests, **601 passed / 4
  failed**, no skips/errors. All failures are the four reference values above;
  all 509 prior tests pass. Do not describe this as a green gate.
- The new file contributes 96 offline tests: 48 value assertions (24 compiled
  DuckDB and 24 reference), 36 multilingual representation assertions, 6 invalid
  encoding checks, 6 provenance/legacy-counterexample/coincidence tests.
- PostgreSQL: **24 passed**, 96 unselected offline/static cases. Read-only role
  grepbit_ro, 24 compiled queries over inline fictional VALUES (plus 48 bounded
  role/timeout SELECTs); no application table read, data mutation or sampling.
  This is SQL-value verification, not a live planner/verifier score.
- No Gemma request: changing the ruler is the current checkpoint, and no model
  call is necessary to establish these failures. Historical 438-call results
  and their artifacts are untouched. No private question, credential, DSN value
  or reasoning text is stored in new artifacts.
- Evidence: `evidence/concept-obligations-v2-01.json`; local test logs under
  `.artifacts/concept-obligations-v2-20260912/`. Earlier dirty work preserved;
  no staging, commit or push.

## Next

The interface question has been sent to the owner: separate required scopes,
prohibited groupings and unresolved obligations, unknown when unresolved or
unbound, research-only, old scores retained. The test-only draft is not a
production decision. Await explicit follow-up before implementing v2.

Repair the existing reference bug and fill nullable-column count generation
before relying on value-oracle comparisons. Then implement and test v2 with
gold obligations separately from model-extracted obligations; begin the bounded
144-call off/on targeted comparison. Larger new-family and joint planner tests
have explicit gates/budgets in the protocol. Best-of-N remains conditional on
measured candidate diversity; it is not an automatic response to these failures.
