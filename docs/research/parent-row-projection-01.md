# Unique-parent attributes: bounded shared-runtime delivery

2026-09-15. Implementation baseline e7986a8. Owner approved the parent ruler and
requested review of the three additional boundaries. Root sole writer. No push,
owner Web restart, persistent DB/schema change or new role. Existing synthetic
IoT/service only, introspection sampling zero; model inputs contain questions,
schema and reviewed overlay, never database rows or reference answers.

## Review disposition and implementation

All three review clarifications were adopted:

1. Preserve the existing filtered/segmented population, before LIMIT/truncation.
   A projected parent can be the segment parent or a different table; one new
   projected source does not mean one JOIN total. Compiler reuses its separately
   compiled population carrier. Self-check receives its join lineage and WHERE
   independently of the final SQL, checks exact LEFT JOIN edges/aliases and
   rejects extra joins, wrong ON, INNER/CROSS, or removed population predicates.
   Existing inferred population links remain available when a single parent PK
   proves multiplicity; their candidate disclosure remains. They do not grant
   permission to project an inferred parent.
2. Reject inheritance expansion on base/used parent relations instead of adding
   ONLY and silently changing the population. Table-local uniqueness does not
   cover inherited rows, as [PostgreSQL documents](https://www.postgresql.org/docs/current/ddl-inherit.html#DDL-INHERIT-CAVEATS).
3. Keep representable single-column FK-to-UNIQUE edges in the common graph;
   require single-column PK only for the new projected parent. Preserve all
   original FK columns for sample exclusion, policy proposals and prevention of
   unsafe reinference when composite/cross-schema edges are omitted.

New internal SchemaTable facts: has_inheritance_children and foreign_key_columns.
They change schema digests and can change contexts on affected schemas. They
are not business definitions or extra planner vocabulary. All **110 historical
Default/fallback contexts on the two measured sources remain byte-identical**.
No claim of identical contexts for arbitrary composite/cross-schema sources.

Details now supports one direct declared parent targeting its sole PK, with
visible projection/join keys, NULL preservation and no DISTINCT. Parent output
keys are flat `table.column`, never nested objects; over-63-byte aliases refuse.
all_columns remains base-only. Parent filters/order, multiple projected parents,
multi-hop/reverse joins and rows+without stay unsupported. Shared ask, policy,
grounding, executor and lifecycle are unchanged owners. No router or second
query system. Existing Details source permission is not broadened to real data.

Compiler revision: plan-compiler-rows-v4-parent-projection. Introspector v3 and
inference v2 retain relation-scope provenance. Explicit prompt v20 changes only
the parent-projection capability instruction; default/fallback instructions stay
unchanged. All 35 integrated messages match the measured candidate exactly.

## Rulers, catalog and values

Review-expanded initial ruler: **15 intended failures, 22 controls pass**. The
approved file moved into normal discovery; negative controls were rerun after
acceptance, not assumed safe from the old blanket parent rejection. Runtime
focused set: **136 pass**, covering same/different segment parent, lifting,
inferred population, hidden table/source key/target key, wrong FK target,
inheritance, two parents, self/multi-hop, flat aliases at 63/64 bytes, ordering,
LIMIT, duplicate parent attributes and NULLs. One old base-only rejection was
removed because its contract was explicitly superseded, not to relax an oracle.

Actual PostgreSQL probe uses TEMP tables owned by grepbit_ro, then switches to
READ ONLY for catalog and compiled SELECT checks. No persistent fixture/data or
grant changes. The only enumeration seam includes LOCAL TEMPORARY tables instead
of BASE TABLE; the FK/inheritance catalog SQL is production SQL. It confirms:
ordinary joined values/names; composite omission with original keys retained;
single-column non-PK UNIQUE usable by aggregate but refused for parent projection;
inheritance producing two matches for one base row and being refused by rows.
Cross-schema omission has mocked contract coverage, **not a created cross-schema
PostgreSQL fixture**. TEMP objects disappear when the connection closes.

Every live answer is compared with independent readonly PostgreSQL SQL. Plans
are also executed on two DuckDB instances preserving fixture identities/FKs but
varying measures with NULL, zero and repeated/tied values. Additional hand-built
contract data include unmatched parents/shared parent values. The same reference
is used across instances; values, projection names, multiplicity and ordering
must agree. This is bounded witness evidence, not full algebra equivalence.

## Natural questions and real consumer

| Phase | Requests | Correct answer | Appropriate refusal | False refusal | Wrong / failed | Physical model attempts |
|---|---:|---:|---:|---:|---:|---:|
| Main + remaining controls | 35 | 20 | 14 | 1 | 0 / 0 | 45 |
| Predetermined targeted repeat | 5 | 2 | 2 | 1 | 0 / 0 | 7 |
| Actual HTTP/MCP exact-response replay | 35 | 20 | 14 | 1 | 0 / 0 | 0 |
| Fresh HTTP/MCP requests | 6 | 4 | 2 | 0 | 0 / 0 | 9 |

**61/100 physical Gemma attempts**, zero transport failures. Replay inputs copied
under serving/main are not additional calls. Six new HTTP requests run the real
Web bridge, stdio MCP, shared ask/compiler/policy/executor and public result
projection on an owned loopback port 18767; its process is closed after the test.
Question/mode/request-ID and exact public projection match. This is actual
consumer transport acceptance, not a new browser visual/interaction test.

The 35-case panel retains 23 old Details cases, gives the newly supported owner
device/site question a **new case ID and prospective qualified output names**,
adds eight parent/boundary cases and three Default controls. Old unsupported
scores are not overwritten. All six supported parent questions answer correctly;
the non-PK UNIQUE example still produces an ineligible planner plan and is caught
by the compiler, not spontaneously understood as unsupported by the model.

Refusal reasons are checked separately: Details aggregate requests can correctly
ask to change mode, without claims of missing-definition detection. The actual
Default MTTR/lease controls refuse semantic_gap and the Chinese without control
answers. The sole false refusal is the old Return/minutes concept_not_mapped gate;
the planner proposes rows and the corresponding List question answers. No word
exception, gate removal, human correction flow or automatic routing is added.

## Costs, errors and non-claims

Ten of 32 Details requests require one repair because Gemma duplicates the
projection as an invalid top-level plan.columns beside rows.columns. Repair
preserves the intended answer, but this costs ten extra calls (45 attempts for
35 primary requests). The sum of model-call durations per primary request has
p50 **2.624 seconds**; this is not full Web end-to-end latency. Three of six fresh
consumer requests also require repair. No permissive discard rule or denominator
change hides these variants. Keep repair-turn cost separate from shape_variants
normalization counts; do not use a low latter number as clean-wire evidence.

Probe corrections are not production/model failures: an initial import failed
before calls; after 32 completed requests the diagnostic pin omitted Default's
legacy-first v15 context, stopping before the next call. Original files are
retained; only the three uncalled controls were run in remaining. Runtime,
question/context and witness identities were unchanged. Repeat verifies the same
runtime and messages with the corrected probe identity. A rename initially made
the verification wrapper's source identity unavailable despite 133 passing
tests; staging the authorized rename fixed fingerprinting, then the pinned
focused gate passed. These are not credited successful experiments.

First broad offline run found one old research test comparing a saved raw schema
JSON literally with today's model_dump including new metadata defaults. The saved
fixture, plans, oracle and historical metrics are unchanged; the assertion now
compares the fixture through current schema validation to the approved ruler.
Final gate results are recorded in the durable evidence summary.
Final validation: **2,286 offline tests pass, zero skips**, static passes;
the schema-compatibility focused group passes 209 tests. No further runtime or
test edits follow this gate; only documentation/evidence closeout.

Known limitations: source-type/catalog facts assume fresh introspection and no
concurrent DDL; inheritance safety is scoped to rows, not a new guarantee for
every older aggregate path. No generalization claim from these known cases, no
full PII/multitenancy deployment approval, no automatic query-kind selection.

## Disposition and follow-up

Accept the bounded unique-parent capability in shared runtime/explicit Details.
The low-risk integration does not require a router or a broad prompt campaign.
Use existing UI for new owner questions; record them under the existing intake
policy. Next address the observed redundant-columns repair cost with a bounded
contract/wire investigation, without silently dropping conflicting columns or
changing the freeze threshold. Keep the construct freeze before adding another
construct. The existing gate false refusal is a separate error family.

Artifacts: `.artifacts/parent-rows-impl/` (ruler, catalog-result.json, main,
remaining, repeat, serving/http-replay, serving/http-live, runtime-focused,
schema-compatibility, static-closeout, offline-closeout). Historical input roots
remain intact. Durable summary: `evidence/parent-row-projection-01.json`.
