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
