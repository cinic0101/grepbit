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

Choose a source and reporting date before submitting. Known fixture dates:

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
