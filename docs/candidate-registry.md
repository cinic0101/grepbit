# Candidate registry (#87, step 1)

Status: implemented offline with rulers. No live call; no change to runtime
behavior, grader, scorer, oracles or frozen assets.

## Why

Until now the accepted contracts pinned the *current* runtime identity as
constants: the P3.10 ruler asserted that the live recipe context equals the
frozen P3.3 fixture, evaluator rulers carried the same hashes and a 25,250-byte
wire witness inline, and the frozen-candidate route tools hard-coded the
semantic digest. Any change to the recipe instruction therefore broke 75 tests
(12 of them evaluator identity rulers, the rest frozen-candidate route tools)
and needed an owner-merged contract change. Identity must be bound to
evidence, not frozen into the checkout.

## What a candidate is

The semantic identity the runtime submits and enforces:

| Surface | Source |
| --- | --- |
| `recipe_context` | `recipe_model.context_identity()`: context, output contract, instruction versions and hashes, system-message hash |
| `structured_output` | `recipe_model.structured_output_identity()` |
| `p1_context` | `model.context_identity()` |
| `limits` | gateway input/request/response caps and call timeout |
| `semantic_identity_sha256` | digest of the four surfaces; equals `p3_candidate_model.SEMANTICS_SHA256` for the frozen candidate |
| `wire_witnesses` | exact request-body digest and byte count for fixed exposed witness questions (the P3.10 E01 English question, with its P1 body, and the development wire witness); never fresh text |
| `runtime_files_sha256` | `grepbit/*.py` digests at registration, informational |

## Files and rules

- `evals/candidates/index.json`: registry version, `current`, and an
  append-only entry list with path, SHA-256 and ancestor. The first entry is
  `p33-frozen-20abb559`, the frozen P3.3 candidate; its values equal the
  P3.10 fixture `tests/fixtures/p310_identity_baseline.json`, which stays
  unchanged as history.
- `tools/candidate_registry.py register --id <id> --note <why>` appends the
  live identity as a new candidate. It refuses an unchanged identity, a
  duplicate id and an invalid id; the ancestor is always the previous current.
  `check` verifies the live runtime equals the current entry (surfaces and wire
  bytes); `show` prints the current entry.
- The chain is strictly linear: each index row's ancestor is the previous row
  and each entry records its ancestor's digest, so rewriting an ancestor in
  place invalidates its descendants. `candidate_sha256` covers the semantic
  surfaces and the wire witnesses, the same surface `check` enforces, so a
  wire-only change (for example the default model name) is registrable.
  **A modified or removed existing file under `evals/candidates/` is a review
  blocker**; the registry is append-only and git history is its audit trail.
  The `note` is one printable line of at most 200 characters and must never
  contain fresh case text or a secret.
- Rulers (`tests/test_candidate_registry.py`): entries are byte-stable against
  the index; the frozen entry equals the P3.10 fixture and the historical
  semantic digest; the live runtime is the registered current candidate; an
  unregistered prompt change fails `check` and can only be registered as a new
  candidate with the previous one as ancestor; tampering is detected; no
  question text is stored.
- Evaluator rulers that pinned the current identity (`RECIPE_IDENTITY`,
  `GENERATION`, the P3.10 semantic and wire assertions, the two byte-count
  witnesses) now read the registered current candidate. Historical P2/v1
  identities in those tests are unchanged.

## How a semantic change proceeds now

1. Edit the runtime (for example one general instruction restatement) and bump
   its version string.
2. `tools/candidate_registry.py register --id <new-id> --note "<reason>"`;
   commit the new entry and the index with the change.
3. The registry rulers and the moved pins pass; the frozen entry and the
   P3.10 fixture are untouched.
4. Evidence tools bind runs to the candidate they observed; historical
   archives keep their recorded identities.

## Not yet covered (step 2 of #87)

The frozen-candidate route tools (`p3_candidate_probe`, `p3_candidate_regression`,
`p3_bedrock_candidate_probe`, `p3_bedrock_observed_regression`,
`p3_reason_diagnostic`) still compare the live semantic identity with the
frozen digest and fail closed on any other candidate; they become historical
readers when the single tiered runner replaces them. Until then a new
candidate cannot prepare packets for those routes, by design.
