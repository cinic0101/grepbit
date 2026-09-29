# Bound comparison context v8 (#79)

The owner approved the bounded proposal in chat: "okay 按照你的建議來進行下一步"
("Okay, proceed according to your recommendation"). The
[recorded grant](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882825384)
requires a v7 baseline before narrowing the proposed repair to reproduced
mechanisms. The independent acceptance of the controls is recorded in
[the panel contract](bound-meaning-controls.md).

## Baseline and scope decision

The single merged-source v7 baseline completed all 24 inputs: 20 correct,
six of eight families correct, no operational failures, 24 client attempts,
163.605099 seconds. E02 English falsely clarified comparison roles.
BM6 Chinese clarified with four choices instead of the accepted three;
BM6 English and Japanese answered rather than clarifying. The latter two
are `missed_clarification` and checked-wrong outcomes, not declines.
All other controls passed. This does not reproduce HA02's false-decline
mechanism, so the count repair surface stops. No holdout text was inspected.

Baseline run ID:
`p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-31b-count-context-v7--e0f6be05d218`.
Report SHA256: `d9216e888200c5c3c1cf8452b77293510fe18158efe64bc083c5be35a4c0eefa`.
Slot: `.artifacts/bound-meaning-controls-20260929/baseline-run`.
Source: `9aa8a11412c03e329021628cf3992c172bf29fef` (PR #111).
Preparation and execution scope:
[recorded preflight](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5883040685).

Root accepts the already-authorized checkpoint narrowed to Compare only.
Candidate `p3-bound-meaning-context-v8` descends from v7; only the following
two context strings and `CONTEXT_VERSION` advance. Count guidance, including
its limitations, is unchanged. This restates accepted grammatical role binding;
it adds no product capability or input-specific routing. Cases, gold, schema,
instruction, native validation/execution, serving profile and limits stay fixed.

## Exact context specification

Context version: `learningops-recipe-context-v4`.

`recipes.compare.scope`:

> Two distinct explicitly supplied full months, with target and reference bound by the question; grammatical binding is sufficient and does not require role labels. All centers; no center filter.

`clarification.comparison_roles`:

> Determine whether the question identifies an evaluated period and a reference period. If it does, bind the evaluated period to current and the reference period to baseline and submit the supported Compare request. Reversing these roles changes a directed question and is not another admissible interpretation. Offer exactly the two reversed assignments only when the question leaves that direction unresolved. Neither chronological order nor mention order alone binds direction. Preserve an explicitly shared year; do not infer a missing year or period.

Intended canonical context SHA256:
`441f901b63d9dfdb6f622351a1e13b8ad3b9308d4c2185fa20a870fb8537ee8f`.
The archived identity ruler must fail at missing candidate registration before
production edits. It checks the exact intended context, ancestry and invariant
instruction/schema/P1/limits/wire boundaries. This static identity evidence does
not test whether the model understands the rule. Commit it before implementation.

## Gates and limitations

After registration, focused/full offline checks and required local/GitHub reviews,
merge into dev. Observe the identical 24 controls once against the v7 report;
all 24 must pass before the conditional 54 dev, 28 frozen regression and
18 holdout regression observations. Existing count failures remain in that gate;
they cannot be waived because this candidate is narrower. A failed gate stops
the sequence, without an automatic new candidate or rerun. The grant ceiling
remains 148 calls including the 24 already consumed. No Sonnet run is included.

These are development controls; results cannot establish fresh generalization
or causally isolate context wording. The original broad-revenue C4 variants
remain unresolved and unmeasured on v7. No original C4 score is repaired here.
Historical candidates and reports remain intact. Recovery from a failed
candidate is to stop observation and retain its evidence; a later restoration
of an earlier runtime requires a new registered identity, not erased history.

## Completed observation and stop

PR #112 merged at `ebabe42d9abf61d023dcdfd829feb30347b03664` after local and
fresh-context GitHub reviews found no blockers. Before merge, 14 focused tests
and the complete 1,246-test offline suite passed. Actual mock wire requests for
all 24 controls fit within the 32,768-byte cap (maximum 28,497 bytes).
The implementation changed one production file, added no operator or repair,
and consumed one bounded candidate attempt. Offline acceptance establishes
identity and contract compliance, not successful model behavior.

The [bound preflight](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5883203259)
preceded one live observation, with the v7 control report as baseline.

| Observation | v7 baseline | v8 candidate |
| --- | --- | --- |
| Correct inputs | 20/24 | 19/24 |
| All-variants-correct families | 6/8 | 5/8 |
| Client attempts | 24 | 24 |
| Elapsed seconds | 163.605099 | 152.164486 |
| Operational failures / timeouts | 0 / 0 | 0 / 0 |
| Checked-wrong inputs | 2 | 3 |

Strict offline report readback passed. The comparison taxonomy is:
19 `UNCHANGED_CORRECT`, zero `FIXED_KNOWN_FAILURE`, one `NEW_REGRESSION`,
three `UNCHANGED_FAILURE`, one `OUTCOME_CHANGED_OTHER`, zero operationally
unassessed inputs. All 24 inputs remain in the denominator.

| Case | v7 | v8 | Classification |
| --- | --- | --- | --- |
| E02_compare.en | False two-role clarification | Same false clarification | UNCHANGED_FAILURE |
| dev-BM2.en | Correct directed comparison | False refusal (`model_declined`) | NEW_REGRESSION |
| dev-BM6.zh-TW | Count clarification with wrong four-choice set | Answer instead of clarification | OUTCOME_CHANGED_OTHER |
| dev-BM6.en | Answer instead of clarification | Same missed clarification | UNCHANGED_FAILURE |
| dev-BM6.ja | Answer instead of clarification | Same missed clarification | UNCHANGED_FAILURE |

The three BM6 answers are checked-wrong: they execute before the unresolved
meaning is bound. The Chinese outcome changed between two failures; do not
miscount it as a newly failing input. Supported-seat, explicit two-choice,
explicit-unsupported and genuinely unoriented-comparison controls stayed
correct in all three languages. These observations do not establish the cause
of a single changed outcome or diagnose HA02's distinct false-decline mechanism.

Candidate run ID:
`p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-bound-meaning-context-v8--654e467e96fc`.
Report SHA256:
`83922e4279aed0c23c68797d640cb0b6a19e7d1c138ac408881cd128edfd5e87`.
Packet SHA256:
`e5f59dc97adbd6535ebae7112152dc0106a826a1ddf3ed9853466e7cf7bbf5a8`.
Slot: `.artifacts/bound-compare-context-v8-20260929/control-run`.
Candidate semantic identity:
`9dc0f3f0dd45ac3d26957503b910139593cd457ff846d468a52f19a692e37e54`.
Both baseline and candidate are indexed `development_observation`; neither
is a golden/fresh result. No raw completion or reasoning was retained.

**The all-24 gate failed. The bounded sequence is stopped.** No 54-input dev,
28-input regression or 18-input holdout follow-up was prepared or executed;
no rerun or additional candidate was made. This grant consumed 48 of its
148-call conditional ceiling. The remaining 100 calls are not independently
executable after the failed gate. The standing formal budget remains 2/4
available; this sequence's conditional holdout observation was not consumed.
v8 is registered current for reproducibility, but is not an accepted improvement
or promotion. No runtime restoration is implied by this evidence-only closeout.

A further repair requires a new bounded proposal and owner decision under the
attempt stop. It should distinguish the persistent directed-comparison failure
from generic-count ambiguity and HA02's unreproduced false decline; this result
does not justify another automatic context revision or changing accepted gold.
