---
name: Correctness or evaluation defect
about: Track an observed failure through reproduction and validation
---

## Observation and scope

- Phase / promised capability:
- Expected meaning and behavior:
- Actual behavior / failure classification:
- Code, fixture/scenario, case/oracle and configuration identities:
- Synthetic evidence (keep real/private evidence out of this public issue):

## Triage and reproduction

- [ ] Classify: semantics / ambiguity / model selection / recipe coverage /
      execution / verification / synthesis / oracle / operational / enhancement
- [ ] Minimal synthetic reproduction demonstrates the old failure
- [ ] Expected semantics reviewed; oracle changes explained independently
- Hypothesis, bounded candidate/attempt budget and stopping condition:

## Validation and disposition

- Fix PR/commit or explicit scope decision:
- Commands actually run and results:
- Targeted, neighboring and protected regressions:
- Production code, operator/repair and config complexity changes:
- [ ] Original source replay confirmed by reporter (or explicitly not applicable)
- Remaining unknowns / reason to keep open:

Do not close a real-data defect solely on a similar synthetic pass. No keys,
connection strings, real names/literals/rows, screenshots or unreviewed traces.
