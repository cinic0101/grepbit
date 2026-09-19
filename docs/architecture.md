# V3 architecture

Decision baseline: 2026-09-18. This describes the agreed direction, not delivered
runtime capabilities. Current implementation includes the P0 fixture/tooling
and the bounded [P1.1 offline scalar kernel](fact-kernel.md), not a planner or
recipe engine. [P1.2](model-integration.md) adds one strict model-to-request
boundary and a prepared smoke runner; no live result or P1 acceptance is implied.

## Goal and boundaries

Deliver checked facts for supported analytical questions. Do not promise "ask
anything", universal correctness, or an automatically improving model. Avoid the
V2 cycle: new case -> new grammar/operator -> repair -> verifier -> interaction.

```text
Reviewed semantic catalog + recipe library
                     |
Question -> Grounding -> Recipe selection/instantiation
                     -> Request semantic contract
                          | clarify / semantic_gap / unsupported / denied
                          v
                     Analytical IR (WHAT facts are needed)
                          v
                     Execution DAG (HOW: queries + derived facts)
                          v
                     SQLite; PostgreSQL from P4
                          v
                     Fact checks -> Fact Pack -> Synthesis
                          v
                     Optional bounded drill-down
```

These are responsibilities, not microservices, separate agents or a required
number of model calls. Start with one process and a small number of modules.

## Architecture rules

1. Own business and analysis semantics; reuse relational representation and SQL
   tooling. SQLGlot is the initial candidate, not a claim of complete correctness.
2. Separate long-lived semantic knowledge from request interpretation and from
   relational execution. Do not build another complete QueryPlan language.
3. Make grain, population, time basis, units, authorization and provenance explicit.
4. Compose simple facts before adding special operators. Growth/share can be
   derived from compatible facts; no obligatory GrowthSpec or ShareSpec.
5. A recipe is a versioned ID + structured template + human-readable explanation,
   not a question-specific report or arbitrary executable config language.
6. Clarification is typed, binding and resumable, not a full reinterpretation of
   an already confirmed choice. Revalidate authorization/config changes.
7. Verification is scoped evidence. A legal plan and consistent SQL do not prove
   that the model chose the user's meaning or that source data is true.
8. All execution goes through a constrained path; no model-generated code bypass,
   unrestricted SQL execution, silent semantic repair or hidden provider fallback.
9. Use mature backend technology without stacking Ibis/DataFusion/Arrow/Polars/
   Substrait in the first version. No fork planned; references remain references.
10. Measure feature-maintenance cost, including config complexity, not just accuracy.

## Contracts, deliberately small

| Layer | Owns | Must not contain |
| --- | --- | --- |
| Semantic catalog | Entities, metrics, dimensions, relationships, populations, aliases, time, units, visibility | Question-specific execution steps |
| Request contract | Bound subject, period, metric meaning, requirements and origin of defaults/choices | A replacement business catalog |
| Recipe | Required/optional facts, parameters, approved follow-up actions | Free-form SQL, per-question exceptions |
| Analytical IR | Instantiated facts, breakdowns, comparisons and output requirements | SELECT, JOIN, CTE, physical plans |
| Execution DAG | Query tasks, fact dependencies, derived calculations, snapshot/budget | Invented business meaning |
| Fact Pack | Values, units, scope, coverage, checks, provenance, missing components | Unqualified "verified true" |
| Synthesis | Claims linked to facts, limits and optional next analysis | New arithmetic, fabricated numbers, unproved causes |

The tiny custom execution layer should primarily coordinate tasks and binding.
Prefer existing SQLGlot expressions for relational work. Do not introduce a
parallel AST abstraction for every SQL construct. Each new primitive needs a
reusable need and evidence that existing composition is inadequate.

## Starting recipes and MVP promise

Overview: core facts plus approved trend/mix/ranking facts.
Compare: the same defined metric over two explicit scopes, with server-derived
change. Breakdown: a reviewed dimension, ranking and an explicit denominator.
A one-fact question need not execute an entire overview.

One datasource per request; SQLite first, PG at P4. Reviewed semantics, typed
clarification, bounded outputs, SQL/parameters and checked facts. One additional
approved drill-down at P4, not an unbounded explore/repair loop. Multiple fact
queries are normal; one analysis need not be one SQL statement. Arbitrary
multi-question decomposition, raw-details products, federation, general workflow
engines, forecasts, causality claims and complete multitenant authorization are
outside the initial promise. Individual future capabilities require explicit admission.

## Verification and execution consequences

Every fact carries its semantic version, source/grain/population, time basis and
range, unit, coverage/truncation, snapshot, dependencies and executed checks.
A request also checks required-fact coverage; ten correct but irrelevant facts
are not a correct answer. Optional failure may yield partial output; missing a
required fact cannot be called a complete overview.

Reconcile only compatible facts. Daily amounts may sum to a total; daily distinct
people need not. Top-k shares need not sum to one. Averages need weights. Shared
omissions can survive reconciliation, so reference/mutation tests stay necessary.

Use a short read-only consistent snapshot for a fact batch. Do not hold a DB
transaction across a model call. Drill-down uses a new snapshot and refreshes
comparison baselines as needed, or discloses incompatibility. No false reconciliation
across snapshots. Apply source/column/function policy, bound values, limits,
timeouts and cancellation in addition to database read-only access.

The model selects desired facts. Synthesis references them and never supplies
missing numbers. Arithmetic decomposition is not causal proof.

## V2 reuse

Reuse lessons about ambiguity, time, units, grounding, false refusal and safety.
Do not import legacy production code, QueryPlan grammar, specialized repairs,
compatibility branches or historical governance machinery. Initial fixture
schema/data/names/questions/oracles are new. Legacy business mappings remain
reference material for a future separately authorized datasource integration.
A V2 comparison is optional later, not a prerequisite that requires rebuilding V2.
