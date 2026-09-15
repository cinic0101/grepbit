# Local streaming E2E interface

This is a development entry, not a deployed or multi-user product. It uses the
real stdio MCP `ask` pipeline; no second model rewrites the result. Progress is
accepted/waiting, not generated answer tokens or inferred pipeline stages.

## Start

Use the existing opaque credential bootstrap described in
[`environment-and-secrets.md`](environment-and-secrets.md). The shell needs
`GREPBIT_SERVICE_DSN`, `GREPBIT_IOT_DSN` (existing readonly fixture role),
`LITELLM_API_KEY`, `GREPBIT_MODEL_BASE_URL` and `GREPBIT_MODEL_NAME`. Do not put
connection values or keys into the browser, registry or command arguments.
Install the locked dev environment with `uv sync` if needed, then:

```sh
.venv/bin/python tools/dev_web.py \
  --registry evals/fixtures/dev_web_datasources.json \
  --confirm-synthetic-fixtures
```

Open **http://127.0.0.1:8765** (not the alternate `localhost` host). `--port`
changes the port; the bind address cannot be changed. Stop the launcher with
Ctrl-C. The explicit confirmation is an operator scope assertion, not automatic
classification or sanitization of an arbitrary database. The supplied profile
contains only existing fictional Service/IoT sources and samples zero values.

For the explicit **Details (individual base records)** mode, use the separate
`--registry evals/fixtures/dev_web_rows_datasources.json` profile. The original
profile stays unchanged and the Details option is disabled there. Default mode
retains the existing strategy for that profile; only selecting Details sets
`query_kind=rows`. Switching sources resets the mode to Default. Counts, sums,
grouped statistics and without queries belong in Default, not Details. Only the
bounded parent-attribute join below is supported; business scopes need definitions. This is
not automatic routing or a guarantee of intent understanding.

The response's query kind belongs to that completed invocation and is displayed
with the question. Source/mode/question/time controls are locked while running.
HTTP-generated failures echo `query_kind` once the mode has been validated;
malformed or pre-validation requests do not echo untrusted input. Backend error
details remain private. The page also retains a text-only, page-memory snapshot
of the submitted question/source/mode/time through rejection, timeout or network
failure. It is labelled "Submitted", not a tool answer or verified interpretation,
and does not change when the user edits the next question. No history is persisted.

Details now also accepts one eligible direct parent's attributes. For example,
on IoT: `列出所有裝置的 device_id 和所在站點的 site_name，按 device_id 排序。`
Each row still represents a device; `sites.site_name` is a flat output key and
may repeat. Only a declared link to the parent's single-column PK qualifies.
Multi-hop/child expansion, parent filters/order and rows+without remain outside
this entry. Missing business scope is still a refusal, not all records.
Updating files does not restart an already running launcher.

The page prefills the suggested reporting date when a source is selected;
switching sources resets it, and you can edit it before submitting. The fixture
guide lists available data, limitations and example buttons (fill only, never
auto-submit). These hints live in `tools/dev_web/examples.json`, not planner code
or automatically inferred business definitions. Known fixture dates:

| Source | `as_of` | Example |
|---|---|---|
| `service_test` | `2026-04-15T12:00:00+08:00` | 工時紀錄共有幾筆？其中有填寫工時分鐘數的紀錄有幾筆？零分鐘也算有填寫。 |
| `iot_spike` | `2026-08-15T12:00:00+08:00` | 離線裝置有幾台？ |

## Behavior and boundaries

- Interpretation, assumptions, warnings, status and verification are visible,
  alongside the result table. NULL is distinct from zero. Truncation is not a
  complete ranking. Reviewed definitions do not certify intent correctness.
- SQL/plan/other public evidence is expandable; the model's raw completions and
  unused candidates are excluded. This projection is not universal PII redaction.
- Query inputs are locked while running. The returned question and request ID
  identify the answer; changing the next question does not relabel an old result.
- There is one active query globally. Another request gets `query_busy` (429),
  without another model call. Stop/disconnect affects only its own invocation.
- Every web invocation owns a fresh MCP subprocess/session. This trades a small
  initialization cost for no stale shared session after a crash; it does not
  create additional planning calls. The next user request starts fresh, never
  silently retries the previous question. The bridge waits up to 35 seconds,
  including startup, with the existing 30-second MCP request budget inside it.
- No shared MCP session is closed to cancel a peer; none is shared in this
  entry. Cleanup cancels the invocation and reaps its child. Remote GPU work may
  still continue; high-load and remote-inference termination are not established.
- Same-origin/Host/header/body checks precede MCP; no CORS, LAN binding, browser
  DSNs, autosave, analytics or query/result logs. Refresh clears page-held state.
  This is not authentication against another process running as the local user.

See [`local-web-01.md`](../research/local-web-01.md) for exact validation and the
remaining browser-control-tool limitation. The known concept gate false refusal
is still present; this interface intentionally exposes rather than fixes it.
