# Fixed-product baseline and A5 audit

Owner approved the next combined baseline/inventory, offline replay and current
product regression stage, requesting conclusions and next recommendations.
Baseline: `b1bcc74`, clean; root owns this bounded measurement. Standing owner
Gemma/read-only PostgreSQL and local-commit authority applies. No push.

## Frozen scope

- Reuse the existing 292 executions / 15 sets from the September 12 panel.
  Preserve case files, legacy references, settings and datasource policies.
- Add one later repeat of six preselected cases, reported separately: POS
  member ratio and engineer salary; no-sampling partial store name; IoT daily
  alerts; feature monthly comparison and quarterly payroll. Not retry-until-pass.
- Maximum 298 scheduled questions and 900 actual model attempts, including
  repair/transport attempts. Serial `gemma-4-31b`, T=0, thinking off, one repair,
  existing 20-second model timeout; no experimental prompt or overlay changes.
- Existing gateway receives only question/schema/reviewed definitions and
  permitted candidate values. Never rows or SQL. Five existing PostgreSQL
  databases use `grepbit_ro`; credentials remain opaque environment values.
  Real POS: sampling 0, `--redact-rows`, metrics/hashed-literal traces before
  first persistence. No persistent DB mutation or new data source.
- Fresh `.artifacts/product-baseline-20260913/`; preserve historical artifacts.
  Stop on source/context drift, budget exhaustion, two consecutive transport
  errors, unsafe persistence, or an unanticipated product-contract decision.

## Separate evidence layers

1. Inventory verifies artifact/source/case identities and the unchanged legacy
   denominator. Historical metrics are historical, not fresh model responses.
2. Replay captured fictional plans through current ask without model calls.
   Audit A5's candidate availability, exact column/id binding and grounding
   policy separately from selecting the correct population/metric. Existing
   authored POS/depot questions and negative/collision controls are sufficient
   for this mechanism audit, not a fresh generalization claim.
3. Run the fixed panel. Keep legacy value matches, accepted refusals,
   status-only passes, wrong answers, and unnecessary refusals separate.
4. Apply unchanged `disclosed-answer-v1` only to predeclared interpretations
   for the already approved engineer/date/comparison/payroll families. Freeze
   their reference SQL before proposals. Preserve legacy results alongside
   these annotations; unlisted recipes remain unassessed. This does not create
   an independently reviewed semantic gold for the remaining panel.
5. Record safe structural traces to localize missing index versus missing hint,
   reference rejection, binding failure, gate refusal and wrong-valid plan.
   No automatic old-verdict carry and no post-result expansion of oracles.

## Exit and next decision

Report every scheduled outcome and incomplete/unknown item; no aggregate claim
that refusals are correct answers. A5 is not accepted merely because hinted
misses are zero: coverage and independent target/value evidence must be shown.
No model/gate/example promotion or new lexical exceptions in this stage.
Reuse the existing 1,796-test/static runtime baseline when its source matches;
validate new private measurement controls separately. Source must stay frozen
during live calls. Then recommend a bounded next step from residual causes;
A4, new holdout and product integration remain subsequent decisions.

## Recovery note

The private driver retained each transport client until the run ended. With
the local 256-descriptor soft limit it stopped with `OSError` after 253 completed
model attempts: 13 complete sets are retained; five service calls have transport
records but no saved outcome report. The original errno was not recorded.
An isolated local descriptor-lifetime reproduction and two success/error close
controls pass. New `resume.py` closes its owned client per invocation (including
repair attempts), preserves initial manifests, checks original source/context/
oracle identity and executes only the remaining 42 scheduled jobs. The five
ungraded partial calls remain counted; at most 647 additional attempts fit the
original 900 budget. This is recovery of a measurement-tool failure, not a
product change or a favorable rerun. Do not claim a clean first-attempt panel.
