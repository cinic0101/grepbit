# v7 regression and denominator audit

Recorded 2026-09-29 Asia/Taipei under [goal #79](https://github.com/cinic0101/grepbit/issues/79).
Two completed observations show that v7 has not converged: the frozen regression
retains E02 English false clarification, and holdout A reveals an English count
clarification regression. No candidate, case, oracle, threshold or serving change
was made in this evidence update. No further run or repair is implied.

## Complete development inventory

The two versioned dev assets contain 57 distinct input IDs across 19 families.
The 51 shared case objects are structurally identical. Keep both C4
families visible in the work inventory:

| Inventory group | Inputs | Families | Current v7 evidence |
| --- | --- | --- | --- |
| Unchanged original dev cases | 51 | 17 | 51 correct in the recorded v2 run |
| C4 explicit contrast (`dev-C4-v2`) | 3 | 1 | 3 correct in the recorded v2 run |
| Original broad-revenue C4 (`dev-C4`) | 3 | 1 | Unresolved semantic acceptance; not measured on v7 |

The v2 panel's 54/54 is a real, complete run, but it does not mean all original
54 questions were repaired. There was no 57-input run; reporting 54/57 as a
measured score or treating the three unmeasured cases as v7 failures would
invent evidence. The inventory is 54 assessed and 3 unresolved/unmeasured, with
historical C4 failures preserved under the old grader and its acceptance concern.
The original C4 family remains open work and cannot disappear behind v2's total.

The [owner-designated independent semantic review](c4-semantic-revision.md)
found that bare revenue/收入/売上 does not entail either exactly the historical
pair or every allowed metric enum. The owner delegated confirmation of the
concrete versioned revision; the reviewer accepted the explicit-contrast trio
before registration. This supplies a rationale independent of candidate output.
It does not resolve the broad-term policy. New semantic acceptance is needed
before making those original questions a valid new scoring gate; preserve the
old cases, gold and results.

## Candidate, exposure and generality

`tools/candidate_registry.py check` passes for `p3-31b-count-context-v7` with
`runtime_files_changed=[]`. Its registered ancestry is v7 -> v6 -> v5 -> v4 ->
v3 -> `p33-frozen-20abb559`. Semantic SHA256:
`95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb`.

The [54-input dev archive](d8-count-context-candidate.md) passed strict offline
readback and its file digest matches the append-only run index:

- Run: `p3-dev-matrix-compare-first-v2--litellm-gemma-4-31b--p3-31b-count-context-v7--5296619ac53c`.
- Slot: `.artifacts/d8-count-context-v7-20260929/run`.
- Report SHA256: `920e2e9e1c76a3c65290c236fb0386deb1187375efa2775593f4e117bf427d25`.

The v7 context contains a general rule preserving specified count requirements
before admitting clarification. It also explicitly maps actual attendance to
`attendance_visits` and names unsupported catalog meanings. It does **not** meet
the suggested stronger constraint of wording without attendance nouns. There
is no D8 ID, language test or phrase-matching branch in the change. Domain
definitions can be legitimate runtime context; these observations do not prove
the rule generalizes independently of those definitions. The new holdout failure
requires investigation, not a declaration that overfitting has been excluded.

FA11 question text was previously exposed to an implementation triage session:
`.artifacts/p36-failure-triage-HdvWjD/exposure-record.json` records all three
FA11 translations and oracle/provenance inspected after the original formal run
under owner-authorized #51 triage. Its source was
`.artifacts/p35-stage-c-pIKdCM/freeze/formal-cases-v2-draft.json`.
We cannot claim the implementing history never saw FA11. This audit inspected
the exposure record, not the frozen question text; it also did not inspect
holdout A question text. Original freeze labels remain historical metadata.
Current runs are explicitly `observed_regression`, never fresh evidence; the
post-formal exposure does not retroactively rewrite the original observation.

## Frozen 28-input observation

Executed once from merged `dev@181cca0485af31443f6eaaa0305775fd5f4a2a9a`
with `tools/evaluate.py`, registered panel `p33-formal-v2`, route
`litellm-gemma-4-31b` and unchanged v7. Baseline was explicitly bound with
`--baseline .artifacts/p35-formal-live-1bekGO/report.json`, SHA256
`be8c381fb8945fbb621962e07b83c6db5e2e44028a72db15729d428b7a7741da`.

Result: **27/28 inputs, 13/14 families**. Exactly 28 client calls,
134.348847 seconds, zero operational failures or timeout. Outcomes: 13 complete
answers, 5 correct clarifications, 9 correct declines, 1 false clarification.

| Comparison against 25/28 baseline | Inputs |
| --- | --- |
| FIXED_KNOWN_FAILURE | 2: FA11 zh-TW and ja |
| UNCHANGED_CORRECT | 25 |
| UNCHANGED_FAILURE | 1: E02_compare.en |
| NEW_REGRESSION | 0 |
| OUTCOME_CHANGED_OTHER / UNASSESSED_OPERATIONAL | 0 / 0 |

FA11 English remains a correct decline. E02 English still asks two
`comparison_roles` choices instead of answering; its actual signature equals
the historical failure signature. This is a repeated observed structure, not
proof of determinism. [Independent disposition #75](https://github.com/cinic0101/grepbit/issues/75)
retains the E02 wording and oracle, so changing either to accommodate this
response is not an accepted repair.

- Run: `p33-formal-v2--litellm-gemma-4-31b--p3-31b-count-context-v7--2e72f2109626`.
- Slot: `.artifacts/v7-regression-audit-20260929/run`.
- Packet SHA256: `8ae76d18d3b1a425edc6710764d47889ac376f6f0a51a641547618d3e62bc56c`.
- Report SHA256: `cf87960cd4b0feb9c55367b9a87b9696d0c6e2dffca3edb521eca21ec5209fff`.
- Grant: [#79 standing grant](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5817980153), now 2/4 of the 31B 28-input runs used.

## Holdout A re-observation

The owner separately authorized one regression re-observation:
"授權一次 holdout A regression" ("Authorize one holdout A regression run").
The [supplemental grant and exact preflight](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882209181)
record the original-language decision and English rendering. Same source,
candidate, route and unchanged 18-input `p3-holdout-a-v2` panel; one attempt per
input, 60 seconds/call, 2,048 output tokens/call and 1,200 seconds/run.

Result: **17/18 inputs, 5/6 families**. Exactly 18 client calls,
111.366850 seconds, zero operational failures or timeout. Outcomes: 3 complete
answers, 8 correct clarifications, 6 correct declines, 1 wrong action.
`HA02_C01_headcount_ctr_b01.en` changed from correct clarification to decline
although clarification is expected. Its zh-TW and ja variants remain correct.

Strict readback of the historical holdout archive
`.artifacts/p381-holdout-a-live-2WYIaE/run/report.json` (SHA256
`47e52eba85f7389479446de80f70aeca53fc0b3bf6bf3235d416bcc8b5dd3914`)
and the new archive yields **17 UNCHANGED_CORRECT, 1 NEW_REGRESSION**, all other
comparison categories zero. This is a separately recorded offline comparison,
not the runner's packet-bound `--baseline` projection: that option accepts
formal/evaluation reports, not the historical holdout report format. Case ID
order is identical and the registered panel pins the original frozen assets.

- Run: `p3-holdout-a-v2--litellm-gemma-4-31b--p3-31b-count-context-v7--3f1f5081f0bb`.
- Slot: `.artifacts/v7-regression-audit-20260929/holdout-run`.
- Report SHA256: `4d102110ac4c528e4014fb204270381ab396494c99b84a73a5399ce052fdf263`.
- Supplemental budget: 1/1 used; original holdout fresh-run budget remains 1/1 used.
- Claim: `observed_regression`, derived by the runner from prior exposure.

## Validation, limits and next action

Read-only SSH preflight matched the prior serving image/config hashes and healthy
31B/gateway. Retries, fallback and cache remain disabled under the existing route
attestation. Both observations use synthetic LearningOps only, opaque credentials,
no raw completion/reasoning retention, no retry/resume, one run at a time.
Total: 46 observed client calls; upstream inference attempts remain unknown.
Both strict archive readers, candidate registration and generated STATE checks
passed. This evidence-only change adds no runtime behavior; the implementation's
1,243-test offline gate belongs to #108 and is not claimed as newly rerun here.

Do not declare convergence or start the next fresh golden observation. First
investigate the two mechanism gaps using closed evidence and independently
authored development controls: already-bound comparison orientation, and true
count ambiguity versus an explicit unsupported requirement. The HA02 regression
is relative to the older holdout candidate and serving state; it cannot isolate
the causal contribution of v7 from intervening prompt/profile changes. Do not
read its question text into an implementing session merely to tune a fix.
Further candidate changes must respect the recorded per-family repair stops.
Original broad C4 remains independent semantic work.

A current v7 Sonnet 28-input packet was prepared offline successfully; no Sonnet
call or budget was consumed. It is a feasibility artifact only and must be
regenerated after source/run-index updates. The #79 grant still requires an accepted compatibility
witness, and its old witness predates the current candidate. The historical
compatibility probe is frozen-candidate-only; preparation support in evaluate.py
does not itself discharge that prerequisite. Versioned current-candidate
compatibility preparation is required before the control run. Remaining recorded
budgets are compatibility 1/3 and observed 2/3. Sonnet is an attribution control,
not a second delivery target. No fresh-generalization, stability, causal or
promotion claim follows from either completed regression observation.
