# Policy A panel versions (#169, step A2)

Step A2 of the plan for the owner's policy A
([#169](https://github.com/cinic0101/grepbit/issues/169)): every executed
Overview states its people-count basis. The owner approved the annex and
oracle revision in principle at #169. This change needs independent semantic
acceptance, and makes no model call.

## The revision

Every Overview answer oracle expects the stated basis
`{"count_basis": "booked_seats"}`, because every Overview answer reports booked
seats. Three dev panels get a new version. Each reuses its predecessor's cases
and oracles files unchanged; only the panel id and the annex change:

| New version | Predecessor | Oracles added to the annex | What they ask |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v4` | `p3-dev-bound-meaning-v3` | `dev-BM5.v1` | booked seats, named |
| `p3-dev-count-fresh-v3` | `p3-dev-count-fresh-v2` | `dev-CF06.v1`, `dev-CF07.v1` | booked seats, named (S) |
| | | `dev-CF16.v1`, `dev-CF17.v1` | a general overview, no count (O, the `dev-A1` class) |
| | | `dev-CF18.v1` | the number of bookings (K) |
| `p3-dev-matrix-compare-first-v4` | `p3-dev-matrix-compare-first-v3` | `dev-A1.v1`, `dev-A2.v1` | a general overview (A1); booked seats, named (A2) |

- **No other expectation changes.** Every oracle already listed stays listed
  with the same expectation. Non-Overview oracles (Compare, Breakdown,
  clarifications, declines) stay unlisted.
- **`p3-dev-mechanism-probe-v2` keeps its version.** All four of its Overview
  answers already expect the stated basis.
- **The predecessors stay** as history, and so do their recorded runs.

## What it means for the runs

- **Under v21.** This is projected from v21's recorded readings on the
  predecessors (#167); it has not been observed on the new versions. v21
  states the basis for an `unresolved` reading, and when the server answers
  a model `count_basis` clarification; neither applies otherwise. So the
  eight added families split:
  - **Already satisfied:** `dev-A1`, `dev-CF16` and `dev-CF17` (9 rows).
    v21 reads them as `unresolved` and states the basis. On the new versions
    they become annex-correct with no runtime change.
  - **Newly failed:** `dev-BM5`, `dev-CF06`, `dev-CF07` (`booked_seats`),
    `dev-CF18` and `dev-A2` (`none`) (15 rows). v21 states no basis for them,
    so they become annex-wrong on the new versions, although they are correct
    on the predecessors.
- **What a v22 gate can show.** With three v21 baseline runs on the new
  versions, the `dev-A1` class shows as `unchanged_correct`, not `fixed`.
  The fixes attributable to the policy are the 15 rows this revision made
  wrong under v21.
  - **Other `fixed` rows** may reflect baseline variance. For example,
    `dev-BM2.en` is flaky on these model bytes (#167).
  - **A `broke` row keeps the gate's `regression` verdict** and is
    investigated, never explained away in advance. One way is to compare its
    validated action with v21's: equal actions point to v22's runtime,
    different ones to model variance.
  - **The dev-A1 class is resolved by the policy,** an expectation change,
    not by a runtime or model change.
  - **v22 is intended to make every Overview state the basis consistently**
    (#175; results in `docs/overview-basis-v22-result.md`).
  - **Report it that way:** improving the grader does not establish product
    improvement (AGENTS.md).
- **The dependency on A1.** A v22 row on a `none` or `booked_seats`
  reading is annex-correct only if the evaluator reads the server's recorded
  statement (#169 A1, PR #173, `docs/recorded-count-assumption.md` there). The derivation
  from the action alone would leave it annex-wrong.
- **The baseline.** Under the three-run baseline rule (#168, merged in #171),
  the new versions start with no runs. The proposed grant adds three v21 runs
  to each new version and two more to `p3-dev-mechanism-probe-v2`, which has
  one, plus one v22 run per panel: 594 calls.
  - **This revises the #169 plan,** which assumed a `p3-dev-mechanism-probe-v3`
    and 616 calls.
  - **The owner confirms the number** before any call.

## Ruler (`tests/test_policy_a_panels.py`)

Committed failing before the panels existed:
- **The panel files.** Each new version equals its predecessor except for the
  panel id, with the same cases and oracles digests. The panel and annex
  digests match the registry.
- **The annex** equals {every Overview answer oracle: the stated basis}. Its
  additions over the predecessor are exactly the oracles in the table, and
  every predecessor entry is kept unchanged.
- **The unchanged panel.** `p3-dev-mechanism-probe-v2`'s annex is already
  complete.
