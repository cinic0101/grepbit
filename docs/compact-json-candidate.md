# Compact JSON instruction candidate (#79)

The owner accepted the minimal-repair and normal-budget verification sequence in
chat on 2026-09-27 ("okay"), recorded in [the goal issue](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5856063963).
The diagnostic [C2.en observation](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855640542)
contained 3,710 consecutive JSON-whitespace characters out of 4,187 characters,
used 2,048 output tokens and returned malformed JSON after 60.881 seconds.
The whitespace location inside or outside a string is unknown.

## One bounded intervention

Register `p3-31b-instruction-v4` as the successor to instruction-v3. Change only
the shared instruction and its version, appending these general serialization
instructions verbatim:

> Serialize the object as compact JSON: do not emit spaces, tabs or line breaks outside JSON strings. Inside strings, preserve required value characters exactly; do not add whitespace padding or repeat characters for formatting.

No case-specific routing, answer example, semantic instruction removal, schema
change, output postprocessing, repair loop, retry, provider setting, or timeout
increase is part of this candidate. Preserve the exact input value characters,
including spaces required within strings. The existing ISO/date validators,
action semantics, runtime context, P1 wire and 60-second/2,048-token limits stay
unchanged. Compact formatting is a prompt intervention, not a decoding guarantee.
It is candidate 2 overall and the first whitespace-directed repair; do not add a
third candidate fix on the same family without the required owner decision.

## Evidence and verification

Commit this contract and archived candidate/order rulers before implementation.
The initial ruler fails because the new candidate and panel are not registered;
these are intended assertions, not setup errors. The candidate ruler checks
exact instruction identity and unchanged other surfaces, not model obedience.
Preserve every prior candidate file, case, oracle, report and threshold.

Register `p3-dev-matrix-compare-first-v1`, an order-only panel sharing the original
case/oracle files and all 54 IDs. Put `dev-A3.en`, `dev-C2.zh-TW`, `dev-C2.en`
first, then the remaining A3/A4/C2 language variants in original order, then the
45 other inputs in original order. A single run checks the proposed sequence
without duplicate sends. Existing timeout/anomaly stops and full denominators
apply; an incomplete run is not a pass.

After offline checks, local and fresh-context GitHub reviews and merge to dev,
bind a new slot to [the existing dev grant](https://github.com/cinic0101/grepbit/issues/87#issuecomment-5852775731).
Run once, at most 54 calls, 60 seconds/call and 3,360 seconds/panel, with the
existing local31B route, synthetic data, no retries/fallback/cache, concurrency1.
Both diagnostic90-second grants remain consumed. Report latency, operational
outcomes and semantic correctness separately; preserve all failures. Improvement
on exposed development data is not fresh quality, stability or promotion.
