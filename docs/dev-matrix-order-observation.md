# Candidate 1 dev order observation (#79)

The first candidate 1 dev run stopped after 23 calls at consecutive Compare
timeouts, before C4 and D8 were reached. Across the three existing dev runs,
9 of 26 Compare calls timed out; none of the other 75 calls did. Returned
Compare calls took about 5.5-10.7 seconds. These observations locate a pattern;
the reports do not distinguish queueing, generation duration or other causes.

Register `p3-dev-matrix-boundaries-first-v1` as a separate development panel.
It references the exact existing `dev-cases-v1.json` and `dev-oracles-v1.json`
and preserves all 54 case IDs, 18 families, language variants and exposure
labels. Only the panel ID and order differ from `p3-dev-matrix-v1`.
D8, C4, C1 and D4 run first, followed by the other non-Compare families;
A3, A4 and C2 run last. This gathers the missing boundary observations while
retaining the original call timeout, failure streak stops and complete-panel
denominators. Candidate 1, runtime, route and all historical assets stay pinned.

This is a new development observation under the existing dev grant, prepared
from merged dev and bound to its own packet and slot. It is not a continuation
or replacement of the incomplete run. Any unrun cases remain unassessed.
A new order can change operational conditions, so an outcome difference alone
does not identify the prompt as its cause. The runner's baseline option needs
matching panel/order; this observation uses no baseline projection. Any later
case-ID comparison must disclose the changed order and incomplete evidence.

The registration ruler checks exact case and oracle equivalence, shared asset
paths/digests, full membership and the intended priority/Compare suffix.
It is static schedule evidence, not a model-quality oracle. Results remain
`development_observation`; they cannot establish fresh quality or promotion.
