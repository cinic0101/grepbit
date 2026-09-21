## Scope

Related issue and phase:

## Changes and evidence

Commands actually run, outcomes and source identity:

## P3 impact review (required for P3 fixes)

Use [the evaluation contract](https://github.com/cinic0101/grepbit/blob/dev/docs/p3-evaluation-contract.md#e-mandatory-system-level-impact-review-for-future-p3-prs).
Record baseline/candidate identities, measured changes or **unknown**, evidence
and blocker/optional disposition for:

- P1/P2 regressions and displaced behavior
- Security/privacy and evaluator/gold isolation
- Grounding candidate provenance and typed choice binding/replay
- Semantic/presentation separation, UI compatibility and block versioning
- Later P1/recipe product-entry routing and route-specific refusal limits
- Prompt/context bytes, tokens, latency and all live/possible attempts
- Production files/lines, operators/repairs, configuration/dependency complexity,
  maintenance and human effort
- Future P4 PostgreSQL and P5 real-data compatibility
- Product promise widened/narrowed and any protected assumption changed

For unrelated changes mark not applicable; do not infer live authorization.

## Boundaries

- [ ] No secrets, private data or generated DBs/raw traces committed
- [ ] Gold/oracle changes have a separate rationale and review
- [ ] Required/optional facts and unsupported behavior are not hidden
- [ ] New operators/repairs/config branches and maintenance cost are disclosed
- [ ] Live execution, when needed, was separately authorized and run locally
- [ ] Unimplemented and unassessed behavior is explicit

Do not merge into `main` without owner approval.
