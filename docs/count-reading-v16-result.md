# Candidate v16: gate result (#146)

Steps (1), (3) and (4) of the grant
[#146 #issuecomment-5913589336](https://github.com/cinic0101/grepbit/issues/146#issuecomment-5913589336)
for candidate `p3-count-reading-v16`
(`docs/count-reading-v16.md`, #147). The baseline is v15 on the same panels:
v15's run from #145 plus the v15 sentinel below.

**Pre-registered verdict: `passed`, on both panels.** This is a development
observation on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v15 sentinels (step 1) | From `dev@a771aab` while v15 was current, repetition 2: 24/24 and 22/22 calls, complete |
| v16 runs (step 3) | From `dev@6e6137c` (the #147 merge, after its round-2 no-blocker review record): 24/24 and 22/22 calls, complete |
| Possible in-flight attempts | 0 in all four runs |
| Grant use | **92 of 92** calls, no repeat |
| Candidate SHA256 | v16 `f6e48dd4b237e0fbdf9003d966db74922748d5f2f8404e850c390a414dafd0f5`; baseline v15 `5ba892e9c024754d6218cc0fbf05415e56960dc57f557776f1b400575f1c5e95` |

| Run | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- |
| v15 sentinel, bound-meaning | `41e3ab0981bdb48d6ae1239540c605d7c66383df861141ae6738664c37f3a100` | `cace280477a259a096da96d37c2b351dc82d96ab94e406431112ae5fbab9540f` |
| v15 sentinel, mechanism-probe | `cb284370f3a4065d25866996feeb02592d803531ee6eaa50a3bf804d08064ea1` | `b08b563c93d2244931ce9309ae07d1f1e074316c96741063fe64720e6643a555` |
| v16, bound-meaning | `76cdf9ebe49bed5fca8e2fc11c98695716b445325f8a66da09a3df9c5aef2371` | `638d4701f54f503a0448f77d906144817e77778e18c93036674abcdf22ca2949` |
| v16, mechanism-probe | `7f9cdb7ef690ef27c457bce4f0c6ce2cc09fab74e3281c348f29cdbddd47c164` | `5c2af233021f575e9631edb353a4257b7d87598017ef5b4efbacc0cd94dadaaa` |

**Authorization order.** Step (1) ran before the owner confirmed the numeric
bounds.
- The owner approved LLM calls without numbers: 「有需要呼叫 LLM 可以核准」. That
  was recorded in the grant comment at 14:43:10Z, together with the agent's
  92-call cap.
- The sentinels ran next, 46 calls, finishing at 15:05.
- The owner's 「ok，繼續」, read as confirming the cap and the plan, was
  recorded at 15:56:56Z (#issuecomment-5914883798), after step (1).
- The agent had written at #142 #issuecomment-5913563185 that the call budget
  would be put to the owner "before implementation or any call". Step (1)
  relied on the recorded blanket approval instead. The cap only narrowed that
  approval, and it was honoured.
- Steps (3) and (4) ran after the confirmation.

**Order and recording.** The timeline below comes from the local packet and
report file times and from GitHub. The reports carry no wall-clock time. A
packet can be built only for the current candidate, and the sentinel packets
name v15 at `a771aab`, where v16 did not exist.

| Time (UTC) | Event |
| --- | --- |
| 14:43:10 | grant recorded: the owner's blanket approval of calls, and the agent's 92-call cap |
| 14:57:28 | #145 merged, with v15 current |
| 14:58:22 | sentinel packets written |
| 15:01 and 15:05 | sentinel reports finished |
| 15:56:56 | the owner's confirmation of the cap and the plan recorded |
| 16:24:20 | #147's round-2 no-blocker review record posted, verified on GitHub before step 3 |
| 16:24:41 | #147 merged, so v16 became current |
| 16:25:13 and 16:25:14 | v16 packets written |
| 16:28 and 16:32 | v16 reports finished |
| 16:33:13 | all four index rows recorded under the grant reference |

As in the v15 cycle, the sentinel rows were written after the candidate became
current. The gate does not limit the recording order (`docs/candidate-gate.md`).
ADR #146's plan ("While v15 is current: one v15 sentinel run") puts the
condition on the run. Calls here are client HTTP attempts;
`upstream_inference_attempts` is null in all four reports.

**The sentinels match v15.** Each v15 sentinel equals v15's #145 run input for
input in outcome, with zero differences: 21/24 and 10/22.

Annex-aware index counts:

| Panel | v15 (2 runs, each) | v16 (1 run) |
| --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 21/24 | **24/24** |
| `p3-dev-mechanism-probe-v2` | 10/22 | 14/22 |

## Gate

The command:

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-reading-v16 \
  --baseline-candidate p3-compare-orientation-v15 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/146#issuecomment-5913589336 \
  --panels p3-dev-bound-meaning-v2 p3-dev-mechanism-probe-v2
```

It gave `evaluation-gate-v1`, verdict `passed`, run index `80452ddf`. Each
panel's baseline is two v15 runs, the sentinel included, and every input was
sentinel-assessed.

| Panel | Fixed | Broke | Unchanged correct | Unchanged wrong | Excluded or unassessed | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 3 | 0 | 21 | 0 | 0 | passed |
| `p3-dev-mechanism-probe-v2` | 4 | 0 | 10 | 8 | 0 | passed |

- **Fixed:** `dev-BM6` in all three languages, on both panels, and `dev-MN1.en`.
  That is 7 rows and 4 distinct inputs. Each was an Overview answer without the
  assumption on v15, and each is now `unresolved` with the stated assumption.
- **Broke:** none.
- **Unchanged wrong:** `dev-MN1` zh-TW and ja, `dev-MN2` ×3 and `dev-MN3` ×3.
  All are false `count_basis` clarifications offering all four count meanings.

## Reading

The typed readings, a post hoc tally from the validated actions:

| Inputs | v16 action | Outcome |
| --- | --- | --- |
| `dev-BM5` ×3 (named seats) | `count_request: booked_seats`, no assumption | correct. v13's spurious assumption cannot arise from this reading. |
| `dev-BM6` ×3 on both panels, `dev-MN1.en` | `unresolved`, with the stated assumption | correct |
| `dev-BM7` ×3 (undecided between seats and accounts) | the model's `count_basis` clarification with the two named meanings | correct |
| `dev-BM8` ×3 (distinct people) | the model's own decline. The server-decline path was not needed | correct |
| `dev-MN1` zh-TW/ja, `dev-MN2` ×3, `dev-MN3` ×3 | the model's `count_basis` clarification with all four meanings | wrong |

- **The code-decided assumption worked wherever the model returned a request.**
  Every Overview request carried the reading the oracle implies, and the
  assumption followed from it.
- **The remaining failures are the prose-decided part.** On the eight
  remaining count inputs, the model still chose to clarify instead of returning
  a request. This is the risk the contract named in advance: "The model's
  `count_basis` clarification remains prose-decided." Its clarification offers
  the whole four-meaning vocabulary, which the instruction already calls "never
  a menu to offer in full".
- **The bookings-clause risks named in advance did not occur.** No count input
  read `none`. `dev-BM6` read `unresolved` on all six rows, and `dev-BM7` kept
  its two-meaning clarification.
- **Nothing else moved.** Against the v15 sentinel, the only outcome change is
  `dev-MN3.en`, from a false refusal to a false clarification; it stays wrong.
  Every Compare input and every other input kept its frozen outcome. The fixed
  inputs were already frozen-correct answers, and only their annex verdict
  changed.

## Claims and limits

- **Scope.** One run per panel, one route, exposed and mostly agent-authored
  inputs. It is not fresh generalization evidence, and it makes no claim about
  holdout or formal panels, Bedrock (which fails closed on v16) or promotion.
- **Server decline untested live.** The server-decline path for a named
  unavailable count never ran: 31B declined `dev-BM8` itself. The ruler covers
  the path offline.
- **Bookings questions are unmeasured.** The bookings clause was not exercised,
  because the gate panels have no bookings-count question
  (`docs/count-reading-v16.md`).
- **What would address the remaining eight inputs.** ADR #146's option B
  (server-built `count_basis` from model-read named alternatives) targets them.
  It would change more frozen tests, and it needs its own owner decision and
  authorization.
- **Budget.** Grant #146's 92 calls are spent. Any further run needs new owner
  authorization.
- **Raw reports** stay local under `.artifacts/v16-sentinel-20260930/` and
  `.artifacts/v16-candidate-20260930/`. The index keeps their digests.
