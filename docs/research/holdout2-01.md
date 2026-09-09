# Holdout 2: the owner's 30 value-grounded questions (2026-09-09)

## Setup

The owner wrote 30 questions without looking at the system, the schema or
batch 1, and put them in `.artifacts/holdout2/questions.txt` (kept out of git
at the owner's request because questions name stores and people).
`evals/questions_to_cases.py` converted them unread; the build side saw no
question before or after the run. Same settings as batch 1: real POS test
database, sampling off, rows redacted, overlay v4, prompt v7, gates on,
`as_of` 2026-02-04 18:00 Asia/Taipei. Nothing was changed between receipt
and the run. Judge: the owner, verdicts given in chat.

Files: `.artifacts/holdout2/{questions.txt,cases.yaml,run.json,review.md,verdicts.yaml}`;
their SHA-256 and the numbers are in `evidence/spike-tier0/pos-real-holdout2-01-tally.json`.

## The four numbers

| Number | Value |
|---|---|
| Correct over 30 judged | 26/30 = 87% (4 answers, 22 accepted refusals) |
| Wrong numbers without an exposed assumption | 4 (q26, q27, q29, q30) |
| Wrong numbers with the reading exposed | 0 |
| Clarify rate / refusal rate | 47% / 73% |
| P50 / P95 | 4.8 s / 6.4 s |

Zero model failures; 31 filter literals checked, 14 matched no row.

## What the batch was made of, by the owner's design

| Group | Cases | Outcome |
|---|---|---|
| Exact stored value in the question (a store, a product, a salesperson) | q01, q06, q07, q18 | answered, judged correct |
| Variant of a stored value: incomplete name, a space inside the name, one wrong character, abbreviation | q02 to q05 (stores), q08 to q11 (products), q12 to q17 (categories), q19, q20 (salespeople) | 14 `clarify` from the literal check, 2 `semantic_gap` from the model (q16, q17, where sibling questions q12 to q15 got a plan and a clarify: the model is inconsistent on whether to filter on a value it cannot see) |
| Ratios | q21 to q25 | 4 stopped by the shape gate, 1 refused by the model |
| Aggregate thresholds (HAVING: groups whose total exceeds a value) | q26 to q30 | the algebra has no aggregate filter, so the planner answered the question without the threshold and nothing in the interpretation or assumptions said so; four wrong numbers, the fifth (q28) was saved only because its value literal also missed |

## What this says

- **The worst class is HAVING, not grounding.** Four silent wrong numbers
  out of 30, all from one missing shape. Every other failure was an honest
  refusal. An aggregate filter belongs in the algebra (a `having` clause on a
  measure alias, compiled onto the aggregate expression) before anything
  else; a language-pack gate cannot separate "products priced over 1000"
  (a row filter, answerable) from "stores with sales over 100000" (a group
  filter) by words alone.
- **Value grounding is class b throughout.** No question repeated the q29b
  pattern (exact value present but cut by the model); every miss was a
  variant spelling. So the exact-substring pre-check alone would have fixed
  none of the 16; what they need is candidate lookup on whitelisted columns
  (contains, prefix, edit distance, space-insensitive) with a unique match
  resolved as an exposed assumption and several matches offered in the
  clarify, plus value aliases for genuine abbreviations. Salesperson names
  are personal data: whether that column is groundable is the owner's
  whitelist decision.
- **The refusal rate of 73% is the honest number** for a batch built to
  probe the two gaps. The literal check did what it was built for: 14 misses,
  0 wrong numbers from them.
- The model's inconsistency on unseen values (filter and let the server
  check, or refuse) disappears once grounding runs before the model call.

## Second run, after `having` (prompt v8)

`.artifacts/holdout2/run-02.json`, verdicts and tally
`evidence/spike-tier0/pos-real-holdout2-02-tally.json` (SHA-256 recorded).
Author sets, batch 1 and smoke unchanged except batch 1 q06 (the recurring
訂單狀態 wobble, deferred by the owner to the next phase).

| Number | Run 1 | Run 2 |
|---|---|---|
| Judged correct | 26/30 | 30/30 (7 answers, 23 accepted refusals) |
| Wrong numbers without an exposed assumption | 4 | 0 |
| Clarify rate / refusal rate | 47% / 73% | 53% / 77% |

The five HAVING questions: q26, q29, q30 now carry their threshold and the
owner confirmed the numbers; q27 chose `category` as base with an average
over `product` (a child table) and was refused as `grain_conflict`, a
wrong-base error to re-verify after grounding; q28's value literal is absent
as written, so the literal check answered `clarify` before execution. q03 and
q16 moved from a model refusal to a literal-check `clarify`: the model now
filters on a value it cannot see and the server catches it, the behaviour
grounding will make uniform.

What "HAVING is solved" rests on: three real questions, unit tests, and the
guard set `evals/cases/tier0/having_pos.yaml` added afterwards (five
threshold cases on the POS fixture with thresholds that split the groups, one
row-filter control): `having-pos-01.json` 6/6, every threshold landed in
`having` and the price condition stayed a row filter. The set joins every
regression from here on.
