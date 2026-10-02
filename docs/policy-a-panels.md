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

- **Before v22.** Under every candidate through v21, these newly listed
  oracles are annex-wrong: v21 states the basis only for an unresolved count
  reading. Under policy A (v22) they become annex-correct.
- **The baseline.** Under the three-run baseline rule (#168), the new panel
  versions start with no runs. The planned grant (#169) adds three v21 runs to
  each new version and two to `p3-dev-mechanism-probe-v2`, plus one v22 run per
  panel.

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
