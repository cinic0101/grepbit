# Small paired language comparison

## Scope and assets

Add Traditional Chinese (`zh-TW`), English (`en`) and Japanese (`ja`) before
P0 review. This adds language coverage, not a new product architecture or a
live-run permission. Keep English documentation and intentional multilingual inputs.

- Base questions and shared expectations: `evals/cases/learningops.json` (wording revision v0.2).
- Paired variants: `evals/cases/learningops-languages.json`, keyed by base case ID.
- Side-by-side review: `evals/cases/learningops-language-review.md`.
- Structural checks: `tests/test_multilingual_cases.py`.

The supplement pins the base catalog hash so edits cannot silently leave stale
translations. The same fixture, reference ID or behavioral expectation applies
to all three variants. A shared expectation is a proposal to review, not proof
that the translations preserve meaning. Do not make three copies of the oracle.

Thirty semantic families provide 87 question variants (29 x 3) plus three
translations of the E10 injected-timeout scenario. E10 is NOT a user prompt or
three language-understanding trials. Q14 remains reference-only; E12 support
remains conditional. This catalog is not a selected 87-call live panel.

## Before P0 review: wording, not model quality

Check naturalness and the preservation of count unit, population, time basis,
cutoff, negation, units, denominator and ambiguity. Keep source entity codes and
stored proper names unchanged. In particular, E04 must not pick a center, E05
must not choose seats/accounts/attendance, and E06 must not acquire a year.
Do not make one language easier by adding definitions absent from the other two.

Revision v0.2 follows the owner-relayed local review of `80109e5`. Japanese
Q06/Q07 now explicitly uses posting time plus successful status. Q13 states
ascending course ID for ties in all languages, matching the unchanged reference;
E09 consistently names session S01. Base catalog and language identities change;
seed, schema, SQL/parameters, numeric and behavioral expectations do not.
Q13's duplicated oracle question metadata follows the wording change. Prior
reports keep their original identities. The focused recheck and owner approval
remain open in #3; do not call this native-speaker or blinded review.

Offline tests check coverage, IDs, protected literals, selected complete cutoff
and top-K phrases, posting/status wording, review-sheet consistency and pending
approval. Deliberate date/top-K and processing-completion text mutations must
fail even when a review sheet could be updated to match. These narrowly scoped
surface guards are evaluator tests, NOT production language rules or semantic
certification. Full equivalence still requires review.

`tests/test_review_witnesses.py` adds an isolated fourth eligible course tied
at the rank-3 cutoff. It distinguishes missing LIMIT, LIMIT 4 and descending
ID tie-breaking without changing the core seed. This is a fixture/reference
witness, not evidence that a model or runtime ranks correctly; omitted tie
ordering may accidentally return the same rows and is not certified by it.

## Later: owner-authorized local model comparison

Once the relevant runtime path exists, start with eight proposed families:
Q01_booked_amount, Q02_booking_count, Q03_booked_seats, Q06_cash_received,
E04_ambiguous_entity, E05_ambiguous_count, E06_ambiguous_year, E07_missing_profit.
This means 24 initial inputs per selected model, not 24 independent semantic
problems. Freeze the final selection and exact budget before the owner authorizes
local execution. Missing runtime capabilities remain not_implemented; do not
substitute a mock planner and call it a language-quality result.

Change only the question language in the first arm. Keep database snapshot,
schema/semantic/glossary/recipe context, prompt, as_of, timezone, model settings
and execution limits fixed. Run each input in a fresh session, do not feed it
another language's answer, and use a recorded balanced/interleaved order. The
same approved glossary (including any aliases) is available to every language.
No per-language prompt rescue or hidden provider fallback within the panel.

The model receives one question and permitted runtime context, never this review
sheet, the complete case record, expectations or reference SQL. Freeze source,
supplement and context hashes along with the commit. Current fixture-check-v1
hashes the base fixture assets, NOT this supplement: retain the unittest result
and supplement hash separately until a real live runner is implemented.

Report per-language outcomes, necessary/unnecessary clarification and false
refusal, operational failures, latency/tokens and per-family discrepancies.
Check semantic alignment (metric/population/count unit/time/entity/required facts),
not exact SQL strings or identical answer prose. Agreement can mean all three
are wrong: report all-three-correct separately from all-three-agree. Keep skipped,
unassessed and failed executions visible, and record all attempts.

A tiny first run is diagnostic, not a statistically established language ranking.
If it exposes inconsistency, predeclare a small repeated panel; never repeat until
one result passes. Localized schema descriptions, translated entity aliases and
natural paraphrases are separate later arms, not extra variables in this baseline.

Use #3 for translation/equivalence review and #4 for local offline reproduction.
Do not add a new issue, verifier or compiler branch merely for each language.
Live execution still requires a separately authorized local-agent request under
`docs/local-execution.md`. No model call or PostgreSQL run is part of this change.
