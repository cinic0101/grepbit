# A5 ratio-output follow-up (2026-09-12)

Owner instruction: "沒問題 可以繼續執行" after grain retirement. Continue
the already-authorised A5 implementation/measurement scope, using the existing
readonly PostgreSQL role and serial Gemma4 gateway. No stage/commit/push,
credential copies, new datasource or A4. Preserve prior uncommitted changes.

Start with an opaque diagnostic on q25, h2_q23 and the authored member-ratio
case: record only allowlisted JSON key structure and error locations before
and after normalisation. No questions, literals, SQL, rows or raw responses
are persisted. At most two runs of each case initially; normal bounded repair
and transport retry remain. This reuses seen cases, not a new holdout.

If the normaliser loses a supplied operand, fix preservation under the existing
contract and add an adversarial synthetic ruler. If the model omits it, first
measure a small generic schema/prompt counterfactual before production edits.
Never invent or infer the missing denominator to pass validation. Any prompt
change gets a separate revision and affected-case regression. Source stays
frozen during every run. New semantic or data-exposure decisions remain stops.

Baseline: dev 746f168 plus prior uncommitted work; ask v3, prompt v15. Elevated
read-only process preflight found no running regression. One local writer.

## Slice result

Completed the six-case structural diagnostic, 18 interleaved prompt trial
cases, 12 synthetic repair-only calls, and four real repair-path counterfactual
cases. None of the tested modifications recovered a defensible end-to-end
improvement. The missing denominator is already absent in raw model output in
the reproduced hybrid-share shape; it is not dropped by normalisation there.
No production prompt or repair behavior changed; A5 remains unaccepted.

Added twelve preservation/fail-closed regression guards. Focused 38, full
offline 355, and static gates pass. Detailed negative results and next bounded
experiment: `../research/a5-ratio-followup-01.md`. Evidence manifest:
`evidence/a5-ratio-followup-01.json`. All model runs have ended; no Git writes.
