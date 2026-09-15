# Details schema adoption and rows-direction adjudication v1

2026-09-16, baseline 91c5b46. Root owns this bounded change. Authority: owner's
"可以開始了" after agreeing to complete untruncated unspecified-direction rows,
with the accompanying review's explicit direction/ranking/limit boundaries.
Earlier authorization covers readonly fixture PostgreSQL, serial LAN Gemma,
local commits, idle local Web restarts; no push or real-data changes.

## Approved evaluation decision, not a runtime default change

`rows-direction-adjudication-v1` accepts ASC or DESC only when a reviewed question
asks for complete details ordered by specified key(s), with neither explicit nor
implicit direction, ranking, top-N, OFFSET, pagination or membership-selecting
limit. Runtime results must have no SQL LIMIT and no service truncation. Preserve
the exact keys, NULLS LAST, stable PK tie-breaker, duplicates and full population;
disclose the actual effective direction. Arbitrary permutations and whole-array
reversal in the presence of NULLs/ties are not alternative oracles.

The reviewer, not a model or a word-list parser, authorizes the interpretation
set. Reuse `evals.answer_acceptance` and its unchanged `disclosed-answer-v1`
wire: separate ordered reference SQL and typed plan for each allowed direction,
context-bound evidence ID for this policy. Explicit/implicit direction gets only
the permitted interpretation; bounded results remain unsupported by this grader.
This does not broaden a frozen real-user test automatically. Future annotations
must precede calls. The current 180-call adjudication is explicitly post hoc,
applies symmetrically, and retains all original responses/scores/thresholds.

Original calls 74/164 omit direction; calls 29/119 explicitly say asc.
OrderSpec currently defaults to desc and that default remains unchanged. SQL
already contains explicit DESC; SQL parser defaults do not explain this result.

## Rulers, then the exact measured candidate

Before production edits: test keys/direction/disclosure, NULLs/ties, multiplicity,
lost rows, LIMIT/truncation and unsupported paging; test the narrowed displayed
schema fails on current production at intended assertions. Existing evaluation
mechanisms may already pass these new behavioral controls. Continue under the
owner's explicit implementation authorization; no additional meaning decision.

Integrate only the measured explicit-rows schema: base_table/rows/filters/order/
limit plus complete refusal branches. Preserve canonical wire, rules, extra=forbid,
normalization and shared OrderSpec; Default/fallback and guided decoding unchanged.
Retain measured revision `details-schema-only-v21-study` for byte-identical
requests despite its historical suffix. No second prompt arm or new dependency.

Verify all 180 saved native requests against production build_messages using the
same effective registry/schema/overlay. Replay actual raw responses where needed;
do not count this as fresh model accuracy. Historical baseline requests retain
their old explicit-rows schema; compare candidate requests to the new production
schema and all Default requests unchanged. Rejudge only the authorized ordering
and existing parent-key corrections, not lease omissions or Return gate failures.

## Service acceptance and freeze exit

Six preselected original requests through actual Web -> MCP -> shared ask:
parent_worklog_status, explicit_minutes_duplicates (S7), kind_minutes_records
(S8), parent_alert_models, kind_critical_count (mode conflict), and
parent_missing_lease. All are Details; Default parity is separately asserted
over the saved requests and focused dispatch tests. Freeze source/tests/probes
before model calls. Use a loopback test Web on an unused port with the existing
rows registry; leave an active user request alone. Maximum six initial requests
and 18 physical completions, counted at the native HTTP request boundary with
opaque upstream key and no credential capture. These fit the prior 240 total
cap after 180 calls. No extra prompt or selective retest if adoption fails.

Adopt only if offline adjudication and request parity pass, no service regression
appears, known S8 remains a gate failure (not a different planner refusal), and
schema variants remain within the existing measured groups' gate. The six smoke
requests validate transport/adoption, not an independent statistical gate group.
Record their raw variants separately, never dilute old denominators.

If adopted, close the measured Details wire blocker for the next conversion
slice. Preserve the <5% per-set rule and unmeasured-group caveats, not a blanket
permanent construct thaw. Lease omission remains an independent Default semantic
defect. Unit conversion public implementation is the next scope, not this commit.
