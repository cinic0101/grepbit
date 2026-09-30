# Reading diagnostic (#79)

Contract `reading-diagnostic-v1`. It is the separate diagnostic call the owner
chose as option (b)
([#79 #issuecomment-5902758076](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5902758076)).
It asks the model, in closed codes, how it read each question: the requested
count, the comparison orientation, the unsupported requirement and the
action. It leaves the current candidate's model-facing bytes, the candidate
registry, oracles, gold and case text unchanged. It is observational: never a
candidate, a gate input, a run-index entry or promotion evidence.

## Why

v12's declines are the constant `{"outcome":"declined"}`, and its answers
carry no reason. So the cause of each failure is inferred, not observed. The
Sonnet control run (`docs/sonnet-v12-control.md`) declined every count input,
while 31B split between answering, clarifying and declining. A closed reading
per input shows whether a model misreads a question or reads it correctly and
then decides wrongly. It also tests whether a stage-split design ("understand,
then decide") could rely on the model's reading.

## Variants

The variant is closed and named in the packet:

- `replayed` shows the model the question and the action it recorded for that
  question in a named source run. It then asks how it read the question when
  it gave that action. The reading is post hoc: a self-report, not proof of the
  cause.
- `fresh` shows the question only and asks for the reading and the action the
  model would take. Its action may differ from the recorded one, and the
  report compares the two.

## Selection (by identity only)

- **Candidate.** The current registered candidate (`tools/candidate_registry.py`).
- **Panel.** A registered `dev`-tier panel. All of its inputs run, in panel
  order; the diagnostic makes no selection.
- **Route.** A registered route. The client is admitted as for
  `tools/evaluate.py --live`: the route decides the provider, model, region and
  timeout. The client's transport security must equal the packet's; any
  mismatch is an `invalid_configuration` anomaly before the first send.
- **Source run.** One indexed run, required for both variants. Its report must:
  - read back and match its index digest;
  - be `evaluation-report-v2` and `complete`;
  - use the same panel, the same route (the report's route object equals the
    packet's) and the current candidate's `candidate_sha256`;
  - for `replayed`, carry a non-null `validated_action` on every input.
- **Packet.** It embeds the canonical evaluation packet that
  `tools/evaluate.py --prepare` would build for the same candidate, panel and
  route. That packet enforces a clean `dev` checkout at the accepted commit,
  the database, panel assets, route settings and route policy.

## Wire

- The **system message** is the production system message, byte-identical:
  `recipe_model.messages_for(question)[0]`.
- The **user message** is one fixed English template, `reading-prompt-v1`,
  given in full below. It carries the question and, for `replayed`, the
  recorded action (canonical JSON, as persisted).
  - It carries no expected branch, oracle, gold, case id or evaluator
    metadata.
  - Each input's user message is at most 4,096 bytes.
- The **response format** is a JSON schema named `grepbit_reading_diagnostic`,
  given in full below, with its SHA256 pinned in the packet.
- The packet pins the SHA256 of each input's two messages. Live refuses a
  message that differs.
- **Call limits:**
  - one call per input, concurrency 1;
  - temperature 0 and `max_tokens` 2,048;
  - no retry, repair, fallback, resend or continuation;
  - the route's call timeout;
  - a run budget of `inputs × call timeout + 120` seconds.

### `reading-prompt-v1`

`fresh`:

```
Diagnostic request. Do not answer the question below. Report only how you read it, as the JSON object required by the response schema.

Question:
{question}

Fields:
- reading.analysis: the supported analysis the question asks for, or none.
- reading.count_request: the count the question asks for; unresolved when it asks for a count whose meaning it leaves open; none when it asks for no count.
- reading.count_event: the event the requested count is about.
- reading.orientation: for a comparison of two periods, whether the question states which period is evaluated and which is the reference.
- reading.unsupported: the requirement in the question that the available recipes cannot meet, or none.
- verdict.decision: the action you would take for this question.
- verdict.reason: the main reason for that action.
```

`replayed`:

```
Diagnostic request. Below are a question and the answer you gave to it. Do not change or repeat that answer. Report only how you read the question when you gave it, as the JSON object required by the response schema.

Question:
{question}

Your answer:
{action}

Fields:
- reading.analysis: the supported analysis the question asks for, or none.
- reading.count_request: the count the question asks for; unresolved when it asks for a count whose meaning it leaves open; none when it asks for no count.
- reading.count_event: the event the requested count is about.
- reading.orientation: for a comparison of two periods, whether the question states which period is evaluated and which is the reference.
- reading.unsupported: the requirement in the question that the available recipes cannot meet, or none.
- verdict.decision: the action your answer took.
- verdict.reason: the main reason for that action.
```

`{question}` is the case question and `{action}` is the recorded
`validated_action` string, each inserted verbatim.

### `grepbit_reading_diagnostic`

In the packet the schema is written with keys in this order:

```json
{"type": "object", "additionalProperties": false, "required": ["reading", "verdict"],
 "properties": {
  "reading": {"type": "object", "additionalProperties": false,
   "required": ["analysis", "count_request", "count_event", "orientation", "unsupported"],
   "properties": {
    "analysis": {"type": "string", "enum": ["overview", "compare", "breakdown", "none"]},
    "count_request": {"type": "string", "enum": ["none", "booked_seats", "known_booking_accounts",
                                                 "attendance_visits", "distinct_people", "unresolved"]},
    "count_event": {"type": "string", "enum": ["not_applicable", "booking", "attendance", "unspecified"]},
    "orientation": {"type": "string", "enum": ["not_applicable", "stated", "unresolved"]},
    "unsupported": {"type": "string", "enum": ["none", "count_meaning", "metric", "period", "scope", "other"]}}},
  "verdict": {"type": "object", "additionalProperties": false, "required": ["decision", "reason"],
   "properties": {
    "decision": {"type": "string", "enum": ["answer", "clarify", "decline"]},
    "reason": {"type": "string", "enum": ["all_supported", "count_basis_unresolved", "orientation_unresolved",
                                          "center_unresolved", "metric_meaning_unresolved",
                                          "unsupported_requirement", "other"]}}}}}
```

`reading` precedes `verdict` in both the declared and the alphabetical order, so
a route that sorts schema keys still asks for the reading first. The schema
uses no keyword that the Bedrock encoding strips (length, pattern, count or
range). Both routes therefore decode the same closed set; unlike the recipe
schema, it is not compacted.

## Persisted observation

Each input's row holds:
- `case_id`, `family_id` and `question_sha256`;
- `state`: `not_started`, `reserved`, `returned` or `failed`;
- `attempt`, `http_attempts`, `elapsed_seconds` and `error_code`;
- the `reading`: exactly the closed object above, or null;
- `usage`: the returned `prompt_tokens`, `completion_tokens` and
  `total_tokens` (each an integer or null) for a returned row, else null.

A response that is not valid JSON (`invalid_json`), or that is valid JSON but
not exactly the closed object (`invalid_reading`), is the model's own content.
- Such a row is `failed` with that code, and the run continues.
- Any other error follows the stop rules.

Nothing else from the response is kept: no raw completion, reasoning, free
text or presentation text.

## Comparisons (computed at readback, never sent)

Readback first pins the panel, cases and oracles files against their
registry digests, and the registry entry against the packet. It then checks
each row's question hash against the panel. A digest or hash difference is
`manifest_drift`; a file that no longer parses fails as `invalid_asset`. For each returned row the report derives:

- `expected_branch`: from the panel case;
- `expected_kind`: the clarification kind of a clarify oracle, else null;
- `recorded_action` and `recorded_kind`: the source run's action class
  (`answer`, `clarify` or `decline`) and clarification kind;
- `decision_matches_expected`: `verdict.decision == expected_branch`;
- `decision_matches_recorded`: `verdict.decision == recorded_action`;
- `reason_matches_expected_kind`: for a clarify oracle, whether
  `verdict.reason` is the reason of `expected_kind`:
  - `count_basis` → `count_basis_unresolved`;
  - `comparison_roles` → `orientation_unresolved`;
  - `center` → `center_unresolved`;
  - `metric_meaning` → `metric_meaning_unresolved`;

  otherwise null.

The summary counts each code of each field, and each comparison's true, false
and null.

## Authorization, slot and stops

- `--bind-authorization` writes the envelope
  `{version, packet_sha256, owner_authorization_reference, run_slot}` with
  exclusive create. The reference must be a grepbit issue comment URL. The
  slot must be a new directory under `.artifacts/`.
- Live refuses a packet, envelope or slot that does not match, or a changed
  source (the rebuilt canonical packet differs), before any send.
- Each reservation is persisted before the client is constructed, so a
  crashed run still shows possible in-flight attempts.
- The run stops at:
  - two consecutive `timeout` errors (`timeout_streak`);
  - two consecutive network errors (`gateway_error`, `rate_limited`,
    `transport_error`: `network_streak`);
  - the run budget (`budget`);
  - any other error except `invalid_json` and `invalid_reading` (`anomaly`),
    for example configuration, envelope, credential or input-size failures;
  - an interruption (`interrupted`).
- An incomplete run, including an interrupted one, reads back with its real
  stop reason and call count. It is reported, not rerun under the same
  envelope.
- **Readback** rejects:
  - a non-integer count;
  - a sent row after an unsent one;
  - a returned row without its attempt or time;
  - a complete run with a row that failed for a reason that stops a run. A
    content error, or one timeout or network error without a streak, lets the
    run continue, so it can appear in a complete run.

## Output and CLI

```
.venv/bin/python tools/evaluate.py --reading-diagnostic --prepare --variant <replayed|fresh> \
    --panel <dev panel> --route <route> --source-run <run id> --db <db> --accepted-commit <sha> \
    --output <new dir>/packet.json
.venv/bin/python tools/evaluate.py --reading-diagnostic --bind-authorization --packet <packet.json> \
    --owner-authorization-reference <grant URL> --output <dir>/authorization.json --run-output-dir <slot>
.venv/bin/python tools/evaluate.py --reading-diagnostic --live --packet <packet.json> \
    --authorization <authorization.json> --db <db> --accepted-commit <sha> --env-file <env file> --output-dir <slot>
.venv/bin/python tools/evaluate.py --reading-diagnostic --report --report-path <slot>/report.json
```

The arguments of each mode are closed. The report's `evidence_class` is
`diagnostic_observation` and `promotion_eligible` is false.

## Claims and limits

- A reading is the model's self-report under a diagnostic framing.
  - A `replayed` reading is post hoc and may rationalize the recorded action.
  - A `fresh` action may differ from the production action.
  - Neither establishes the cause of a production decision.
- The production system message says the user message is question data, not
  authority to change the instructions. The diagnostic user message is such an
  instruction, and the model may weigh that conflict.
- Comparisons against expected branches and clarification kinds reuse
  existing accepted oracles. The diagnostic adds no expected reading; reading
  fields without an oracle counterpart are reported, not graded.
- The results describe these development inputs on this route and candidate,
  not other inputs or models.
