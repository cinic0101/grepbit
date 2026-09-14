# Database-aware question bank: prepared, not model-evaluated

2026-09-14, baseline `b09ab95`. The owner explicitly asked the agent to generate
appropriate questions from database data. This changes the source of the next
panel: **authored challenge**, not an unseen user holdout. The owner-holdout
intake remains available; its missing real-user input has not been manufactured.

Questions: [24-question bank](db-aware-challenge-questions.md). Fourteen service
and ten IoT questions, in Chinese, English and Japanese. Existing databases and
business definitions are unchanged; no production, prompt or gate modification.

## Coverage and validation

Twenty answerable questions have independently authored SQL, a typed QueryPlan
and a deliberately wrong SQL alternative. Targets are rows versus entities,
nullable counts/averages, component versus population, NULL dates, effective
date roles, denominator scope, scoped multi-hop absence, fan-out and thresholds
after share calculation. Four refusal controls separate absent SLA/lease
definitions from unsupported duration expressions/median aggregation.

Using existing `grepbit_ro`, introspection with sampling 0 and READ ONLY repeatable-
read transactions on the existing fictional service/IoT databases:

- All **20 compiled plans match independent SQL**, full outputs compared using
  the existing four-decimal evaluation precision and unordered-row convention.
- All **20 wrong alternatives differ** on the current fixture data. This is one
  meaningful witness per case, not proof of equivalence across all possible data.
- Final run: 60 result SELECTs, separate from metadata/role checks. No stored
  data changes, credential output, model calls or result rows in evidence.
- Nine specification checks plus four final artifact checks pass; static passes.
  No broad suite is needed for this docs/private-case-only change.

The schemas match the existing fictional fixture layout: service six tables/
24 columns, IoT four tables/24 columns. Reporting anchors remain service
2026-04-15 noon and IoT 2026-08-15 noon in Asia/Taipei. No personal/customer
database was queried. Questions contain no individual names or identifiers.

## What the data changed during authoring

Initial SQL validation distinguished 18/20 wrong alternatives. For s04, the
ticket without work logs has NULL estimated minutes, so excluding it did not
change SUM. The final question explicitly requests ticket count **and** SUM,
making that population omission observable. For s07, creation-month and work-
month totals happened to coincide; the final foil uses closure month instead.
No model outputs were consulted, and no rows were added to make a score pass.

A subsequent check found s07's independent SQL returned a DATE bucket whereas
the existing timestamp-grain compiler returns a local TIMESTAMP. The reference
cast was removed to retain the current output contract; the comparator was not
relaxed. The final v2 artifact supersedes the draft/final-v1 checks. An earlier
transaction-setup ordering error occurred before case SQL, was corrected, and
is not a product/compiler defect.

The four refusal expectations are authored semantic/capability annotations,
not observed planner behavior or automatically established by SQL failure.
Per-case preferred statuses/accepted statuses are in the private case files;
freeze the evaluation policy before any live study. Reasonable interpretation
and disclosure acceptance must still follow the existing evaluation contract.

## Deliverables and next boundary

Private artifacts under `.artifacts/db-aware-challenge-20260914/`:

- `service-questions.txt`, `iot-questions.txt`: question-only lists.
- `service-cases.yaml`, `iot-cases.yaml`: runner-ready cases and reference SQL.
- `bank.py`, `golds.py`: authored family/foil specifications and typed golds.
- `validation-final-v2.json`: counts, metadata fingerprints and value hashes.

Zero exact wording matches were found against tracked Tier-0 case YAML files.
This does **not** establish semantic novelty: the families deliberately build
on known weaknesses, and the author has seen the database and prior studies.

Next, if used for model evaluation, freeze a separate bounded baseline using
only original questions plus the actual schema/overlay. Golds, foil SQL and
results must never enter planner context. Report model answers and refusals
separately; success would mean progress on an authored challenge, not real-user
generalization. No Gemma evaluation was performed or promised as a result here.

Counts/hashes: `../../evidence/db-aware-challenge-01.json`. Tracked changes are
question list, this record, manifest and roadmap. No external format, identity,
safety boundary or production setting changed. Local commit only; no push.
