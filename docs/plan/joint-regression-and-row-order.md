# Joint-policy regression and independent row-order repair

2026-09-15, root owner, clean baseline `e5c2c2c`. User accepted the proposed next
steps with "好 沒問題": wider one-call regression, then independent sorting/gate
work. Existing explicit grants allow checkpoint decisions, psql/Gemma calls and
local commits without renewed approval. No push. No Web promotion this slice.

## Ordered work and authority boundaries

1. Freeze unchanged `query-kind-joint-v1`; paired fresh v15 and joint on all 64
   IoT/Service/coverage/adversarial controls. Reuse the established spike runner
   and its original scoring. Do not change production/evals while these run.
   Preserve typed failures and accepted refusals separately from values.
2. Ruler for rows ordered by an unprojected **visible base-table column**:
   allow a validated column name, qualify SQL to the base; retain projection,
   multiplicity, NULLS LAST, specified direction, PK ties and bound LIMIT.
   Unknown, hidden and foreign-table order keys refuse; hidden keys are never
   authorized by the new form. Aggregate ordering remains output-only.
   Record ordering refs in semantic_refs and existing actual-order disclosure;
   do not add the key to returned columns or silently drop ordering.
   First establish red behavior tests, then root may approve implementation
   using the original autonomous-checkpoint grant. Additive row-plan contract
   change only; no PII/authorization relaxation or new persistent format.
3. After old-control runs stop, repair the row compiler/validator/normalizer.
   Version the opt-in row prompt independently and pin the old v16 messages
   in the research driver so old studies remain reproducible.
   Read-only PostgreSQL replay and small live sorting controls distinguish
   calculation repair from the still-active lexical gate.
4. Gate work is evidence consolidation only this slice. Existing source-scoped
   gate research already released wrong answers when disabling absent concepts.
   Do not repeat it, add a Return exception or disable the gate. State the
   smallest unsolved request-role evidence problem and retain counterexamples.

## External budget and verification

At most **180 actual model calls across this slice**, including repair/retry:
paired 128-question calls first, then bounded regression repeats/sort probes.
Existing internal Gemma 4 31B only, serial, T=0, thinking off; only synthetic
questions and visible schema/overlay/candidates sent, never rows/SQL/oracles.
Opaque .env key and read-only grepbit_ro via env DSNs; synthetic IoT/Service
only, sampling 0, bounded SELECT, no admin or DB mutation. Local artifact scripts
may refer to the existing password file but never copy or print its value.

Artifacts `.artifacts/joint-regression-20260915/`; increment meter before every
call, source/panel fingerprints, fresh per-run outputs. Focused tests during
iteration; one broad static/offline closeout. Failed or truncated runs are not
semantic passes. No new provider, router framework or normal datasource opt-in.

## Executed checkpoint and closeout

Original permission sources: user granted "同意你可以在 checkpoint 決定接下來的方向",
"有需要呼叫 psql, gemma 都沒問題" and "有需要時隨時可以 commit 不用特別問我".
This record describes that authority; it does not grant additional authority.
The current "好 沒問題" accepted this bounded next-step sequence.

Row-order ruler: six intended `plan_order_field_unknown` failures and four safety
controls passing in `order-ruler/`. Root exercised the existing checkpoint grant
to proceed after the paired live process stopped (125 calls). No identity,
authorization, persistent schema, aggregate ordering or response shape changed.
Only the opt-in row sort contract widened to visible base columns; explicit sort
verification and v17 row prompt followed. Thirteen completed row-order rulers,
two known gate sentinels and the existing suites pass.

Finished at **167/180 actual calls**, no DB writes. Follow-up used fresh processes,
shared ask with 30-second lifecycle, unchanged historical research messages
(exact reconstructed-baseline comparison), independent typed PostgreSQL replay.
Static and offline pass: 2,028 tests, zero skips. Results and remaining promotion
blockers: `../research/joint-regression-and-row-order-01.md`.
