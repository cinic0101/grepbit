# Behaviour identity (ADR #164, option C)

The owner chose option C of ADR #164 in chat on 2026-10-01, and the agent
recorded it at
[#164 #issuecomment-5934122486](https://github.com/cinic0101/grepbit/issues/164#issuecomment-5934122486):
「選 C」. This document is the contract for its implementation. It makes no
model call and changes no candidate.

## Why

`candidate_sha256` covers only the model-facing surfaces and the wire
witnesses (`docs/candidate-registry.md`). A change to the runtime's decision
rule, the code that turns a model action into an answer, a clarification or a
decline, therefore could not be registered or gated without also changing
model-facing bytes.
- **v19 needed such a change to register.** The outputs are close to
  deterministic, and the change most likely flipped one unrelated input
  (`dev-BM2.en`). The gate then gave `regression` (#162).
- **v20 restored v18** (#163).

Option C keeps both meanings of "the same candidate":
- **the same model input,** `candidate_sha256`, unchanged;
- **the same system behaviour,** the new behaviour identity.

## The behaviour identity

For any registry entry, and for the live identity:

```
behavior_sha256 = sha256(canonical_json({"candidate_sha256": …, "runtime_files_sha256": {…}}))
```

- **`canonical_json`** is `grepbit.model.canonical_json`: sorted keys, no
  whitespace, UTF-8, no NaN. This is the encoding the registry already uses for
  its other digests.
- **`runtime_files_sha256`** is the digest of every `grepbit/*.py`, which every
  entry already records.
- **No format change.** The behaviour identity is derived from fields every
  entry already records. No entry, no index row and no `registry_version`
  changes, and historical entries keep their recorded identities.
- **Historical behaviour identities.** Computed for the 19 registered entries,
  they keep today's same-bytes groups exactly:
  - `p3-31b-count-context-v7`, `p3-v7-context-restoration-v10`,
    `p3-v10-restoration-v12` and `p3-v12-restoration-v14` share `3c9b06ed…`;
  - `p3-count-scope-v18` and `p3-v18-restoration-v20` share `7cc96145…`;
  - every other entry has its own.

  So no historical pooling or gate selection changes.

`tools/candidate_registry.behavior_identity(entry)` computes it. `show`
prints it.

## What uses which identity

| Use | Identity | Change |
| --- | --- | --- |
| `register` refuses `identity_unchanged` | behaviour | was model input. A runtime-only change is now registrable. |
| `check` (the live runtime is the current candidate) | model input, failing; runtime files, listed | unchanged |
| `--prepare` and `--live` (packet build and its rebuild) | model input and runtime files | **new refusal:** `source_identity_failure` when `check` lists any changed runtime file |
| `--gate`: the `same_bytes` refusal, the baseline runs and the candidate runs | behaviour | was model input. Version `evaluation-gate-v2`. |
| `--gate`: each report's recorded identity (`candidate_identity`) | model input | unchanged: a report records only `candidate_sha256` |
| `--aggregate`: the included runs | behaviour | was model input. Version `evaluation-aggregate-v2`. |
| `--replay`: `candidate_bytes` | model input | unchanged: replay feeds recorded model actions through the current code, so only the model input must match |
| Diagnostics: the reading diagnostic, the routing upper bound and the count ablation | model input | unchanged: they study the model's reading of the same input |
| `STATE.md` | both | the current candidate's line also shows its behaviour digest |

**Why prepare and live now refuse a runtime drift.** A run is attributed to its
candidate's behaviour identity through `candidate_id`. A packet built while
`grepbit/*.py` differs from the current entry would attribute the run to a
behaviour the runtime did not have. Until now, this rested on process alone: a
merged `dev` commit, plus the current candidate's ruler asserting
`runtime_files_changed == []`.

**The gate and aggregate outputs:**
- **The gate** adds `behavior_sha256` to its `candidate` and `baseline` objects.
- **The aggregate** adds it to its `candidate` object.
- **The refusal code** `same_bytes` keeps its name, for compatibility. It now
  means that the two behaviour identities are equal.

## What this enables, and what it does not

- **A runtime-only candidate** (for example v21: v20's model-facing bytes plus
  v19's server answer) can be registered and gated against v20.
- **Its model-input identity equals v20's,** so replaying v18's or v20's
  archives under it is allowed. Replay is an offline prediction, never a gate
  input.
- **The cost.** A runtime change with no behavioural intent, such as a kernel
  fix or a refactor, is also a new behaviour identity. It needs a registration,
  and the baseline pooling ends there. The current candidate's ruler already
  required this through `runtime_files_changed == []`, but before this change
  such a registration was impossible.
- **Not part of this contract:** v21 itself, its frozen-test amendment, the
  exception to the two-fix default, and its grant. Each needs the owner (#164).

## Ruler (`tests/test_behavior_identity.py`)

Committed failing before the implementation and passing after it, in the same
PR:
- **The formula.**
  - `behavior_identity` equals the formula above, computed independently, for
    every registered entry.
  - The two same-bytes groups share one identity each, and every other entry
    has its own. The pinned values are v7's group `3c9b06ed…`, v18's group
    `7cc96145…` and v19 `37185c31…`.
- **Registration:**
  - A runtime-only change registers as a new candidate, whose `candidate_sha256`
    equals its ancestor's. The live identity is patched so that one runtime file
    digest differs, in a temporary registry.
  - The same behaviour again is refused with `identity_unchanged`.
  - A model-facing change still registers.
- **Prepare** refuses `source_identity_failure` when `check` lists a changed
  runtime file.
- **Gate and aggregate:**
  - On a twin registry, a runtime twin (the current entry's model-facing
    identity with one runtime file digest changed) is not refused `same_bytes`
    against its sibling. A same-behaviour twin still is.
  - Baseline selection includes only same-behaviour runs; model-input selection
    still includes both.
  - The versions are `evaluation-gate-v2` and `evaluation-aggregate-v2`, and the
    outputs carry `behavior_sha256`.
- **Unchanged identities:** `check`, `--replay` and the diagnostics keep
  selecting by model input.
