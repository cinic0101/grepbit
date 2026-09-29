# Mechanism probe development controls (#79)

The owner approved the lean diagnostic in chat, selecting
"核准精簡版診斷（新 dev 面板約 19 題、獨立驗收、v8 單次 ≤24 calls）"
("Approve the lean diagnostic: new dev panel of about 19 inputs, independent
acceptance, one v8 run of at most 24 calls"). The
[recorded decision](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5884332817)
pins the [proposal](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5884331188).
This is a diagnostic of the registered current runtime, not a candidate.
Runtime, context, instruction, schema, validators, kernel, serving profile,
limits and every existing case, oracle, candidate and report stay unchanged.

## Questions the panel answers

After the [failed v8 gate](bound-compare-context-v8.md), three failures remain
distinct: E02 English directed comparison is falsely clarified on every 31B
observation; generic count ambiguity (BM6) is answered or given an ungrounded
choice set; HA02 English's false decline is unreproduced on dev. Each decline
is the constant `{"outcome":"declined"}`, so its cause is not observable.
The route samples at temperature 0 and P3.7 recorded no flips, so this panel
varies inputs instead of repeating them.

## Panel contract

Register `p3-dev-mechanism-probe-v1`: 22 inputs, 14 families, one fixed order.
All inputs are exposed development material. Five existing cases and their
oracles are reused byte-for-byte: `E02_compare.en`, `dev-A3.en`, `dev-BM2.en`
and `dev-BM6` in three languages. No holdout question text or oracle payload
is read; G3's attendance-compatible framing derives only from HA02's published
choice-set metadata.

| Group | Family | Single change from its anchor | Expected |
| --- | --- | --- | --- |
| G1 | `E02_compare` (en) | Anchor, reused | answer current=March, baseline=February |
| G1 | `dev-MC1` | `compare with` -> `compare against` | same |
| G1 | `dev-MC2` | `did` -> `does` | same |
| G1 | `dev-MC3` | `overall` -> `across all centers` | same |
| G1 | `dev-MC4` | year stated on both months | same |
| G1 | `dev-MC5` | `compare with` -> `change from` | same |
| G1 | `dev-A3` (en) | Passing exposed contrast, reused | same |
| G2 | `dev-BM2` (en) | Anchor, reused: year on reference only | same |
| G2 | `dev-MY1` | year stated on both months | same |
| G2 | `dev-MY2` | year stated on target only | same |
| G3 | `dev-BM6` | Anchor, reused: booking overview plus headcount | clarify: seats, accounts, people |
| G3 | `dev-MN1` | overview without booking framing | clarify: proposed four meanings |
| G3 | `dev-MN2` | booking count only, no overview | clarify: proposed three meanings |
| G3 | `dev-MN3` | bare headcount only, no framing | clarify: proposed four meanings |

G1 and G2 are English only because the observed failures are English only;
their other languages already pass on v7 and v8. G3 has zh-TW, English and
Japanese variants. Compare answers use the all-center confirmed booked amount
with the existing fixture values; count clarifications use CTR-A01, March 2026,
Asia/Taipei full month. Count choice sets are authored proposals: the
independent reviewer decides them from each question before registration and
may reject a variant. A rejected variant is dropped, never rewritten after any
result. Scripted responses test evaluator plumbing, not a model.

New assets are `evals/dev/mechanism-probe-{cases,oracles,panel,responses}-v1.json`.
Commit this specification and its ruler, failing at the missing panel, before
registering assets.

## Observation and pre-registered readings

After semantic acceptance, offline checks and local/fresh-context GitHub
reviews, merge into dev and observe the panel once with `tools/evaluate.py`
on `p3-bound-meaning-context-v8` against no baseline. Bounds from the recorded
decision: route `litellm-gemma-4-31b`, witness `gemma-31b-xgrammar-compact-v1`,
at most 24 client calls, one in flight, one attempt per input, 60 seconds and
2,048 output tokens per call, 1,560 seconds per run; synthetic data only;
retries, fallback and cache disabled; no raw completion or reasoning retained.

All results are `development_observation` with the full denominator.
Readings fixed before the run:

- G1: variants that answer while E02 still clarifies localize the lexical
  factor; if none answer, no single factor is identified. In either case no
  Compare text revision or phrase rule follows. The next options are accepting
  a documented 31B limitation or a separate structural decision.
- G2: `dev-MY1` answering while `dev-BM2.en` declines supports the year-placement
  reading of v8's regression; otherwise that regression remains unexplained.
- G3: a decline of an attendance-compatible English input (`dev-MN1.en` or
  `dev-MN3.en`) reproduces an HA02-class false decline on dev and permits a
  separate, single-surface count repair proposal. If none decline, HA02 stays
  an observed regression with an unknown mechanism and that repair surface closes.
- G3 answers and choice sets characterize seat-default and full-menu behavior;
  no repair follows from this run alone.

Stops: any operational, credential, route or privacy anomaly. No rerun, no
automatic candidate, no gold or oracle change, and no regression, holdout or
Sonnet run follow from this observation. The observation is not causal proof:
it runs one context identity and cannot isolate v6/v7/v8 wording.
