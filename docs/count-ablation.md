# Count ablation diagnostic (#152)

Contract `count-ablation-v1`, step (2) of the grant
[#152 #issuecomment-5925246940](https://github.com/cinic0101/grepbit/issues/152#issuecomment-5925246940)
(owner: 「我沒問題了，可以開始」). It tests two root-cause hypotheses for the
current candidate's (v18) two stable failures. It sends the production system
message changed by one pre-registered variant, a fixed set of edits, and grades
the reply through the unchanged production pipeline.

It is observational: never a candidate, a gate input, a run-index entry or
promotion evidence. It leaves the runtime, candidates, cases, oracles, panels
and annexes unchanged.

## Hypotheses (#152 #issuecomment-5925190411)

- **H-A1, labels.** `dev-A1` (a general booking overview) reads
  `count_request: "unresolved"` because the enum labels carry more weight than
  the prose. An Overview answer always contains counts, so `"none"` looks
  wrong and `"unresolved"` reads as "not specified". If H-A1 holds, renaming
  the labels moves `dev-A1` to a no-count reading, while the generic counts
  keep the assumption.
- **H-C1, rules.** `dev-C1` (a people count with doubt about the system's
  basis) gets a two-choice `count_basis` clarification because two older rules
  still require one literally:
  - the context's `count_basis` entry;
  - the instruction's either/or rule.

  Both were written before the owner's #149 ruling. If H-C1 holds, scoping
  those two rules to the user's own undecided choice moves `dev-C1` to an
  answer, while `dev-BM7` (the user's own undecided choice) stays a
  clarification.

## Inputs (pre-registered)

Every case of these families runs, in each panel's order, under both variants:

| Panel | Families | Inputs |
| --- | --- | --- |
| `p3-dev-bound-meaning-v2` | `dev-BM5`, `dev-BM6`, `dev-BM7` | 9 |
| `p3-dev-mechanism-probe-v2` | `dev-MN2` | 3 |
| `p3-dev-matrix-compare-first-v3` | `dev-A1`, `dev-A2`, `dev-C1` | 9 |

Each input runs under each variant: 21 × 2 = **42 calls**, one per input and
variant. There is one run per panel: 18 + 6 + 18. The grant's step (4) says
"one ablation run". The agent reads it as this one pre-registered set of 42
calls, in three per-panel runs, each with its own envelope and slot; that
reading is recorded on #152.

**What each input is for:**
- the targets are `dev-A1` (H-A1) and `dev-C1` (H-C1);
- the controls are `dev-BM5` (named seats), `dev-A2` (bookings and seats),
  `dev-BM6` and `dev-MN2` (generic counts that must keep the assumption), and
  `dev-BM7` (the user's own undecided choice, which must stay a
  clarification).

## Variants (pre-registered, exact)

The base is the current candidate's production system message: the
instruction plus the canonical runtime context. Each edit must occur exactly
once in the base text. Otherwise preparation is refused (`variant_text`), so a
different candidate cannot silently receive a different edit.

**`labels`** (H-A1).
- **The schema.** The structured-output schema's Overview `count_request` enum
  maps `"none"` to `"no_people_count"` and `"unresolved"` to
  `"generic_people_count"`. The other values are unchanged. The runtime
  context's `output_schema` is that same schema.
- **The instruction** gets six edits. Compare's `orientation:"unresolved"` is
  untouched.

  | From | To |
  | --- | --- |
  | `"unresolved" when it asks for a count whose meaning it leaves open` | `"generic_people_count" when it asks for a count whose meaning it leaves open` |
  | `"none" when it asks for no count, including` | `"no_people_count" when it asks for no count, including` |
  | `so it is none, never known_booking_accounts` | `so it is no_people_count, never known_booking_accounts` |
  | `the server answers an unresolved count with booked seats` | `the server answers a generic_people_count reading with booked seats` |
  | `Overview request and count_request "unresolved", not a count_basis clarification.` | `Overview request and count_request "generic_people_count", not a count_basis clarification.` |
  | `is also answered with count_request "unresolved", and the stated assumption` | `is also answered with count_request "generic_people_count", and the stated assumption` |

- **Edit 4 changes more than a label.** It also changes the noun: "an
  unresolved count" becomes "a generic_people_count reading".
- **The reply.** Before the production pipeline reads the reply, its content's
  Overview `count_request` is mapped back by the inverse table, so the
  unchanged pipeline validates and grades it.
  - The envelope and the content are parsed with the production parser
    (`protocol.strict_json`).
  - A reply that production would reject passes through byte for byte, and the
    unchanged pipeline grades it. That covers duplicate keys, non-finite
    numbers, lone surrogates and excessive nesting.
  - Mapping never raises, and any other reply also passes through.
  - A reply that uses a production label (`none` or `unresolved`) under
    `labels` falls outside the variant schema. It passes through and is graded
    as given.

**`rules`** (H-C1). The schema is unchanged, and the reply passes through byte
for byte.
- **The instruction:** `An explicit either/or contrast restricts the open
  interpretations to that contrast, even after an earlier generic noun.`
  becomes `An explicit either/or contrast restricts the open interpretations to
  that contrast, even after an earlier generic noun; a question about which
  count basis the system uses is not such a contrast.`
- **The context `clarification.count_basis`:** `Use count_basis only when the
  question explicitly leaves the count basis undecided between named meanings,
  offering exactly those meanings.` becomes `Use count_basis only when the user
  says they themselves have not decided between named meanings, offering
  exactly those meanings; a user who doubts which basis the system counts by
  has not left it undecided.`

## Wire, grading and records

These follow `tools/routing_upper_bound.py` (`docs/routing-upper-bound.md`),
except that the variant replaces the narrowed context and the comparison has
no verdict:
- **Packet.** The packet embeds the canonical evaluation packet for the current
  candidate, the panel and the route, with a clean `dev` checkout at the
  accepted commit. It pins:
  - each variant's instruction, context and schema digests and its edits;
  - each input × variant message digest.
- **Calls.**
  - The route is the 31B LiteLLM route only.
  - One call per input and variant, with concurrency 1.
  - The route's call timeout, and a run budget of `calls × timeout + 120`
    seconds.
  - No retry, repair or fallback.
- **Stops.** A route anomaly stops the run, as do two timeouts or two network
  failures in a row.
- **Grading.** The reply, after the `labels` mapping, is served to
  `recipe_model.interpret_recipe_and_execute` by a replay client and graded by
  `p3_grading.grade` against the case's oracle.
  - On an annex panel, the row's annex verdict is `evaluate.annexed` over the
    persisted validated action.
  - Each row also records the reading: `count_request`, or the clarification
    kind and its choice count.
  - Each row records `mapped`: whether `map_back` changed the reply's bytes.
    Only a `labels` row can be mapped. The flag is recorded at run time and
    cannot be recomputed on readback.
- **Authorization.** One envelope binds the grant comment and one run slot.
- **Readback.** The report reads back from the slot.
- **Unassessed rows.** A returned row whose grade is an operational failure is
  `unassessed`, under the candidate gate's rule (`_gate_unassessed`), never
  `wrong`.
- **The selection.** The packet contract derives the pre-registered rows from
  the packet's canonical packet. Readback ties them to the registry:
  - the canonical inputs must equal the pinned panel's inputs;
  - every row's question and variant messages must match the pinned panel.
- **Comparison.** Each row is compared with the current candidate's own
  recorded runs of the same bytes on that panel: the baseline's assessed and
  correct counts per input, annex-aware.
  - It applies the candidate gate's integrity checks in `routing_upper_bound`'s
    order. Each refusal is closed: `no_baseline`, `baseline_unavailable`,
    `candidate_identity`, `inputs_differ`, `index_mismatch`.
  - There is no verdict.
  - **From a clean clone.** A clean clone has no baseline archives, so the
    in-run readback gives `baseline_unavailable` rather than an error. Copy the
    run slot back byte for byte, then re-read it with `--report` in the checkout
    that holds the archives.

## Commands

```bash
.venv/bin/python -m tools.count_ablation --prepare --panel <dev panel> --route litellm-gemma-4-31b \
  --db <fixture.sqlite> --accepted-commit <merged dev commit> --output <dir>/packet.json
.venv/bin/python -m tools.count_ablation --bind-authorization --packet <dir>/packet.json \
  --owner-authorization-reference <grant comment URL> --output <dir>/authorization.json --run-output-dir <slot>
GREPBIT_LLM_PROVIDER=litellm .venv/bin/python -m tools.count_ablation --live --packet <dir>/packet.json \
  --authorization <dir>/authorization.json --db <fixture.sqlite> --accepted-commit <merged dev commit> \
  --env-file .env --output-dir <slot>
.venv/bin/python -m tools.count_ablation --report --report-path <slot>/report.json
```

The tool runs as a module (`-m tools.count_ablation`), not as a script.

## Reading rule (pre-registered)

For each target and its variant:
- **The target moves** if its variant verdict is `correct` in at least two of
  its three languages. Its baseline is wrong in every recorded run.
- **A control breaks** under a variant if both hold: its baseline is correct in
  every assessed run, with at least one assessed run; and its variant verdict
  is `wrong`.
- **Inconclusive:** fewer than two of the target's three rows have an assessed
  variant verdict (`correct` or `wrong`), or any control row under that variant
  lacks one (unassessed, failed or not started), or a target or control has no
  assessed baseline run. Unassessed and operational failures never count as
  `wrong` or `correct`.
- **Supported:** not inconclusive, the target moves, and no control breaks
  under that variant.
- **Mixed:** not inconclusive, the target moves, but a control breaks.
- **No support:** not inconclusive, and the target does not move. The verdict
  is per hypothesis and says nothing beyond this wording.

## Claims and limits

- **Single samples.** Each input and variant is one sample at temperature 0.
  A change suggests a cause; it does not prove one.
- **Labels mapping.** Mapping the `labels` reply back is a deterministic
  rename, and it is disclosed. It never repairs a reply that production's
  parser rejects. By design, it does make a reply that uses a variant label
  valid for the production schema.
- **Known limit: tied to the current code.** As with `routing_upper_bound`,
  readback recomputes the variant pins and messages from the current code.
  After any runtime change, an archived report fails readback with
  `variant_text` or `invalid_manifest`. Read the results while the candidate is
  current.
- **What a null result means.** A variant that moves nothing gives no support
  to its hypothesis, for this wording only. It does not refute the hypothesis.
- **The rules variant is not only a scoping.**
  - It adds a directive to the either/or rule. Its `count_basis` text repeats
    v18's edit 3 (system-basis doubt) inside the context.
  - Its wording, "the user says they themselves have not decided", echoes how
    `dev-BM7` is phrased, which biases that control toward staying a
    clarification.
  - So a move under `rules` cannot be attributed to the older rules alone. It
    shows that stating the distinction in those two places changes the action.
- **Not a candidate.** A variant that moves a target is evidence for a v19
  design. It is not a candidate: the frozen clarification test pins the
  `count_request` enum, so a `labels`-style candidate needs the owner's
  frozen-test approval.
