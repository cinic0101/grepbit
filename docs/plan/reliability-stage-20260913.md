# Bounded reliability stage

Status: COMPLETE. See `../research/reliability-stage-01.md` and
`../../evidence/reliability-stage-01.json`. All 288 scheduled executions finished
within 288 transport attempts; no production candidate passed the promotion
criteria. The bounded research outcome is complete, not a product-release claim.

Owner: root. Baseline: `3c7b48f`. Authority: the owner's approval to organize,
implement and validate this stage, standing permission for Gemma/read-only
PostgreSQL and local commits; no push. No human-correction interface.

## Frozen experiment

- A: 24 authored grounding questions, public POS stores and fictional depots;
  index absent/present, two repeats: 96 question executions.
- B: 24 component-versus-row questions (payroll/bonus, goods/tax,
  service/surcharge; four intents; Chinese/English). Baseline, date-role,
  component-role and neutral factual metadata; two repeats: 192 executions.
- C: offline replay of pre-existing labeled concept minimal pairs, current
  lexical gate versus concept-only veto disabled. Other guards remain intact.

Freeze questions, admissible recipes, independently authored value oracles,
synthetic instances, model payload hashes, source identity and execution order
before calls. Two repeats reverse arm order. Multiple synthetic instances must
distinguish component exclusion from row exclusion. Unknown recipes remain
unassessed; do not count refusal as an answered question or numerical coincidence
as semantic equivalence. C selects its corpus before observing shadow outcomes.

Budget: 288 question executions and at most 864 actual transport attempts total,
not per arm. Serial Gemma 4 31B, temperature 0, thinking off, existing one repair
turn. Stop at two consecutive transport errors, source/context drift or privacy
failure. No leftover budget borrowed from prior studies. No provider responses,
private rows, credentials or bound DSNs persisted. Only approved public store
names and fictional data may be model literals. Introspection sampling is zero.
Endpoint and credentials follow `environment-and-secrets.md`; runtime DB role
is `grepbit_ro`. No database setup, schema COMMENT or persistent data mutation.

## Decision gates and end

A requires every designated uniquely resolvable case to work in both repeats,
with no false substitution, ambiguous/missing guess, exclusion reversal, privacy
failure or newly confirmed wrong answer. B requires repeatable benefit across
domains/languages without harming genuine row-filter requests; date-comment-only
or equally strong neutral-context changes do not establish a component mechanism.
C measures false vetoes avoided against wrong answers newly admitted; it does
not authorize removing the production concept gate.

Research drivers/tests stay under `.artifacts/reliability-stage-20260913/`.
Persist aggregate results and reproducibility hashes in research/evidence files.
Promote only candidates meeting their predeclared gates. Production contract
changes still need their applicable ruler checkpoint. If none qualifies, close
with a negative result rather than adding a speculative fix. Candidate promotion
requires affected live regression and a separately bounded full regression;
this study alone is not a release gate. Authored cases are not a fresh user
holdout. The unavailable 30–50 unseen-user-question validation stays explicit.

Closeout: focused driver/oracle/safety tests, relevant existing offline tests,
static gate; full offline gate only if shipped implementation changes warrant it.
Report exact completed calls, errors, refusals, unknowns, value disagreements,
disclosure and treatment effects separately. Local commit, never push.
