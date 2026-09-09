# Glossary

- **tier-0**: answering from the introspected schema alone; every answer is
  `unverified_semantics`.
- **tier-1 / overlay**: reviewed knowledge layered over the schema (metrics as
  plan fragments, absent concepts, aliases); answers can be `verified`.
- **QueryPlan**: the closed algebra the model fills with identifiers and typed
  literals; the only thing the model produces.
- **PlanCompiler**: validates a plan against the schema and renders SQL as a
  sqlglot AST with bound placeholders.
- **grain_conflict**: the compiler's rejection of a dimension or filter on a
  table not reachable by foreign keys away from the base table (would fan out
  or has no path).
- **inferred foreign key**: a join found by a name rule plus zero-orphan value
  containment; carried as a candidate assumption.
- **semantic_gap**: the question names a concept the datasource cannot
  express; **unsupported**: the shape is outside the algebra or the request is
  not a data question; **unsafe**: a write or dangerous request;
  **clarify**: two readings are equally plausible, or a concept is unmapped.
- **concept drop**: the failure where the planner ignores a qualifier it
  cannot express and answers a broader question; the one wrong-answer class
  that matters.
- **coverage audit**: an experimental second model call mapping question
  concepts to plan elements; measured unreliable, not in the product path.
- **language pack**: cross-datasource word lists (unsafe words, unsupported
  shapes) used by the zero-call fast paths.
- **as_of**: the timestamp relative time expressions are resolved from, in
  the business time zone, always by the server.
- **shape repair**: coercing a column reference the model wrote as a string
  into `{table, column}` when exactly one table matches; meaning is never
  guessed.
