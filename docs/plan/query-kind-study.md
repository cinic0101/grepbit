# Query-kind and answerability study

2026-09-14, baseline `70dba41`, clean tree. Root owns research implementation,
tests and interpretation. Original user authorization: "幫我找出如何 在規劃時就
區分聚合與明細，並保留缺失定義的拒答能力；是否需要獨立分流呼叫，則由實驗決定，
不先擴建架構". Earlier grants authorize autonomous checkpoint decisions,
psql/Gemma calls and local commits; no push. No production/registry changes.

## Hypothesis and bounded design

Answer shape and support are distinct: a listing can require missing rental
identity; an aggregate can be fully defined. Neither a type label nor a model
claim of support certifies intent. Existing latest/without encodings can also
list entities, so route labels are `rows`, `legacy`, `decline`, not a lexical
"list"/"count" split. No business keywords, new metadata, retrieval or gate
relaxation. Same original question, as_of, visible schema and overlay in all arms.

- A direct: unchanged row-enabled v16 prompt, one initial planner call.
- B joint: same v16 plus a generic cardinality/support policy, same PlanProposal
  wire and one initial call. Revision `query-kind-joint-v1`.
- C split: policy and full visible context produce a small RouteDecision;
  decline stops, legacy invokes unchanged v15, rows invokes unchanged v16.
  Revision `query-kind-router-v1`. Only a rows plan can pass a rows route and
  only a non-rows plan a legacy route. Mismatch is operational invalid, not a
  necessary refusal. Builders may refuse despite an affirmative route.

All use shared ask(), gate, grounding, compiler, SQL policy and one 30-second
RequestControl. Router malformed output is failed, never guessed or repaired
into another route; usual planner shape repair remains bounded and counted.
No server/public wire, authentication, persistence or identity changes.

## Frozen panel and scoring ruler

32 synthetic/seen or newly authored cases: 12 existing row cases (one excluded
joined listing), eight existing missing-definition negatives, six selected
legacy controls (one sibling-fact negative), six new contrasts. New cases are
NOT user holdout/generalization evidence. Keep families together in reporting.

Run independent SQL oracles before model calls. Compare complete typed values,
row multiplicity and prescribed ordering; row cases also require exact column
names. Aggregate aliases are not meaning. Do not use lossy serialized report
rows. No per-result reference choice or partial-column scoring. Historical
scores stay unchanged. A necessary refusal requires a semantic refusal status;
invalid/timeout is failure, not credit. Report correct answers, incorrect answers,
necessary refusals, unnecessary refusals, operational failure, calls and latency.
Matched result on one DB does not establish semantic equivalence.

Rulers before implementation: decline stops construction, kind mismatch fails,
cancel stops next stage, joint changes only research messages, duplicate/NULL
and ordering mismatches fail, missing-definition answers fail, gate remains.
Under the original autonomous-checkpoint grant, inspect red ruler results and
then implement; no further approval is inferred from this work record.

## External scope and stop rules

At most **160 actual model calls**, including repairs/retries, to the existing
internal Gemma 4 31B gateway; serial, temperature 0, thinking off. Opaque .env
credential, no other provider. Only fictional questions and existing visible
schema/overlay/candidates sent; never SQL, reference labels or result rows.
Local PostgreSQL synthetic IoT/Service, grepbit_ro, enum limit 0, bounded read-only
oracles and shared SELECT execution. No admin, schema writes or customer DB.
Freeze source/panel before live; save each result and call meter incrementally.
Output `.artifacts/query-kind-study-20260914/`, sanitized durable evidence.

No arm is promoted automatically. Split must improve final answers without
new unjustified answers or excess refusals relative to joint; otherwise prefer
the simpler one-call candidate (if itself acceptable), or reject both. A second
call is a hypothesis to test, not a design requirement. No full router framework.

Pre-live validation note: the first test collection lacked the new module;
that import failure is not ruler evidence. An interface-only scaffold then
recorded nine not-yet-implemented behaviors, not a production-contract
violation. Implementation passed 58 focused checks before two additional
scoring/router-negative tests. All changed runtime logic is under evals/;
the public error enum is unchanged (research details are separate fields).

During the initial run, after observing MTTR's joint refusal, freeze eight
sentinels for a fresh-process repeat if at least 32 calls remain: original
device details, MTTR, leased fees, tickets without logs, NULL-minute count,
rented-device rows, VIP-site rows and minutes-only records. Repeat all three
arms unchanged; total across both processes remains at most 160 calls. This
is a targeted stability check selected during research, not a held-out test.

## Literature informing, not deciding, this experiment

- [DIN-SQL, NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/file/72223cc66f63ca1aa59edaec1b3670e6-Paper-Conference.pdf), sections 4.2/5.3:
  classification chooses construction strategy and ablations compare it with
  one prompt for all difficulties. Its easy/non-nested/nested SQL classes differ
  from our routes; its results do not prove Gemma needs two calls.
- [TrustSQL](https://arxiv.org/html/2403.15879v4) explicitly compares pipeline
  and unified approaches and feasible/infeasible requests. This motivates
  separate wrong-answer/refusal accounting, not adoption of its aggregate score
  as our product threshold.
- [EntSQL, June 2026](https://arxiv.org/html/2606.03363v1) evaluates enterprise
  knowledge beyond schema. It reinforces keeping business-definition support
  separate from structural plan validity; we do not add new knowledge in this
  routing ablation.

Prior operator-restriction experiment (2/8) and failed unsupported-only fallback
remain negative evidence. This test changes WHEN the route is chosen and compares
it with a one-call policy; it does not claim independent semantic certification.

## Closeout

Main 32-case run: joint and split each 18 correct answers, 12 necessary refusals,
one unnecessary refusal and one invalid output; split costs 55 calls vs joint's
33. Eight-sentinel repeat reproduces the outcome differences. Total **155/160**
calls, zero DB writes. Prefer the one-call candidate for broader regression,
not a production promotion. Residuals are the existing unprojected sort-key
restriction and the Return/returns vocabulary gate. See
`../research/query-kind-study-01.md` and `../../evidence/query-kind-study-01.json`.
