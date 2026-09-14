# Name occurrence study (2026-09-14)

Root owns this research at `c349881`. The owner explicitly approved continued
research, root-decided checkpoints, psql and Gemma in this turn. Existing local
commit authority continues; no push. The unchanged Claude PID was previously
explicitly exempted by the owner; no Python regression is running. No delegation.

## Question and bounded intervention

Current `ValueIndex.mentions` flattens normalized matches into column/value pairs
and drops shorter names globally when they occur inside a matched longer name.
Rule 11 describes these as verbatim occurrences. That description is too strong:
colliding stored spellings can both be offered for one source occurrence. This
study separates a truthful rule from occurrence provenance, not another intent
verifier or an automatic union/selection repair.

Three arms on 24 authored questions (12 behaviors in each of two fictional
schemas): A unchanged messages; B same candidates/wire, truthful normalized-hint
rule; C B plus request-local occurrence metadata. C does not add candidates that
the current hint path dropped. Candidate recall and provenance coverage are
reported separately. Exact spelling, explicit sets, repeated names, overlapping
short/long names, unresolved positive/negative names, absent negative names,
unfiltered totals and explicitly requested normalized sets are controls.

Occurrence data are evidence of text matching, not predicate role or intent.
The research-only extractor maps normalized characters back to source ranges,
keeps separate occurrences, suppresses shorter contained hits only at the same
location and distinguishes exact from normalized-only candidates. Exact source
spelling narrows candidates for that occurrence. The source question and catalog
are request-bound by hash; a changed request cannot reuse the catalog. No new
public format, identity token, automatic gate or persistent state is introduced.
Normalization that cannot preserve a trustworthy source map is unavailable,
not guessed. Boundary rules are explicitly limited character heuristics.

## Ruler and root checkpoint

First tests: repeated/overlapping mentions; collision alternatives; exact source
precedence; catalog permutation; casefold expansion; normalization uncertainty;
cross-request/cross-column/invalid-range rejection; no source span as proof of
business role; closed controls distinguishing explicit sets from alternatives.
Use a static baseline assertion when no production occurrence interface exists;
do not call an import failure a red ruler. Root may proceed after meaningful
specification evidence, recording the checkpoint result here.

Freeze case questions, expected plans/independent SQL, foils, messages, source
hashes and model configuration before live calls. Preserve historical scores.
Reuse the existing disclosed-answer grader with complete predeclared scalar
SUM variants; unknown recipes stay unassessed, not wrong by shape alone. Across
four value instances a plan must match one consistent permitted interpretation.

## External and stop limits

Root checkpoint passed: `ruler-red-v2.xml` has nine intended assertion failures
and four passing controls, no setup failures. The baseline occurrence stub
returns unavailable; this is an unimplemented research interface, not nine
production defects. Two passing assertions independently show the existing flat
hint overclaim and global short-name loss. Proceed with the research helper only.
Before live freeze, one hand-counted source offset was corrected (28, not 27).
The initial prefix fixture was also rejected during calibration: a one-character
short-name typo has a unique existing fuzzy resolution, so labeling it mandatory
refusal would overstate the oracle. The frozen prefix is shared by the two
colliding full spellings and has equal candidate scores. No live outcomes existed
when these ruler/fixture corrections were made; the earlier JUnit files remain.

At most 72 initial / 144 actual calls including one validation repair, Gemma4
31B at the existing gateway, serial, T=0, thinking off, timeout20 seconds.
No transport retries; stop after two transport errors, drift, unsafe output or
budget exhaustion. The model sees only fictional schema/definitions, authored
questions and approved fictional names/provenance, never SQL/results/real data.
Use the existing ignored key opaquely. Raw model output is hashed, not saved.

Read-only PostgreSQL on localhost with `grepbit_ro`, opaque DSN environment:
inline VALUES oracle checks only. No stored customer rows, account creation,
persistent writes or new provider. DuckDB is in memory. Research helpers and
bound synthetic witnesses stay in `.artifacts/name-occurrence-20260914/`;
publish counts/hashes and decisions only.

A candidate needs at least two wrong-answer rescues across both schema contexts,
no loss of correct controls and no new known wrong answer before a separate
confirmation experiment. A formatting/annotation gain does not qualify. This
screen is not a generalization test: these are authored schema/wording variants.
If baseline ceiling, finish the offline diagnosis and skip that candidate's
live comparison. If the screen fails, stop; do not build a framework or patch
one word to rescue the demonstration.

## Closeout decision

The corrected preflight has 18 passing tests. Seventy-two jobs / 78 actual calls
completed, six validation repairs and zero transport errors. B replaces the two
negative wrong answers with `invalid_structured_output`; this is failure, not a
rescue. C preserves all four wrong answers. Neither candidate passes the screen;
do not spend the remaining ceiling on repeats or promote either prompt/provenance
surface. Primary artifacts/source are frozen and unchanged.

Two separate counterfactual tests show that a blanket multi-candidate-occurrence
gate catches four mandatory-refusal cases but also blocks two explicitly requested
normalized sets. No such gate is implemented. The source range hash binds textual
inputs/catalog content, not a tenant, nonce, predicate role or user confirmation.
Short-name hint loss is independently observed, but both live overlap questions
already answer correctly through ordinary literals; it is not a measured rescue.
No public identity contract, runtime behavior, API, persistence or safety boundary
changes. See `../research/name-occurrence-01.md` for evidence and remaining limits.
