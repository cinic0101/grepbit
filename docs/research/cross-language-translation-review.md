# Translation-only review, cross-language study v1

2026-09-12. These are the 12 fictional/authored development questions, not
customer data. Translations are captured from the 48-attempt study under
`.artifacts/cross-language-study-20260912/live.json[l]`.

This sheet was drafted after reading only T outputs and the automatic fidelity
ledger, before inspecting Z1/Z2/E plans or their correctness. It intentionally
does not reveal planner outcomes. The root's linguistic impression is that
these are plausible translations; that is an LLM opinion, not human confirmation.
Please check counting unit, included/excluded population, negation, ratio
direction, quoted output labels and preservation of ambiguity. A translation
must not silently decide what an unspecified return rate means.

Agent review status: **all 12 preserve meaning**, in response to the owner's
request "你可以幫我檢查嗎". This delegates linguistic review to the root; it is
not owner/human confirmation or approval to adopt the method. The initial
translation-only impression preceded planner analysis; this final written
agent review follows it and is not an independent blinded review. The live
ledger remains immutable (2 reference-exact, 10 unreviewed under the frozen
rule). Input/translation hashes are preserved in the ledger and the separate
agent-review section of `evidence/cross-language-study-01.json`.

| ID | Original | Captured translation |
|---|---|---|
| output_count_all | 回傳交易筆數。 | Return the number of transactions. |
| output_count_returns | 回傳退貨交易筆數。 | Return the number of return transactions. |
| output_amount_all | 回傳所有交易的總金額。 | Return the total amount of all transactions. |
| output_amount_returns | 回傳退貨交易的總金額。 | Return the total amount of return transactions. |
| label_only | 統計所有交易筆數，欄名用「退貨統計」。 | Count all transaction records, and use the column name "退貨統計". |
| label_and_filter | 統計退貨交易筆數，欄名用「退貨統計」。 | Count the number of return transactions, and use "退貨統計" as the column name. |
| negate_grouping | 不要按會員分組，只給會員交易的總筆數。 | Do not group by member, just provide the total number of member transactions. |
| negate_population | 不要計入會員交易，只給非會員交易的總筆數。 | Do not include member transactions; provide only the total number of non-member transactions. |
| service_rows | 回傳所有工時紀錄的總筆數，同一工單有多筆紀錄就各算一筆。 | Return the total count of all work hour records; if there are multiple records for the same work order, count each as one. |
| service_entities | 回傳有工時紀錄的不同工單總數，同一工單只算一次。 | Return the total number of unique work orders that have labor hour records, counting each work order only once. |
| rate_unspecified | 退貨率是多少？ | What is the return rate? |
| rate_count_defined | 退貨交易筆數除以所有交易筆數，比例是多少？ | What is the ratio of the number of return transactions divided by the number of all transactions? |

## Review findings

- `output_count_all` and `output_amount_all`: imperative "Return" remains an
  instruction to output a result, not a restriction to returned merchandise.
- `output_count_returns` and `output_amount_returns`: retain the return-only
  population and distinguish transaction count from total amount. "Return
  transactions" is understandable in this POS context, although less natural
  than "transactions involving returns".
- `label_only` and `label_and_filter`: keep the literal label `退貨統計`; the
  former counts all records, while only the latter filters to return records.
- `negate_grouping`: prohibits grouping by member without excluding members.
  `negate_population`: excludes member transactions without inventing a
  grouping instruction. The two negation scopes remain distinct.
- `service_rows`: explicitly counts each work record, including multiple
  records on one work order. `service_entities`: counts distinct work orders
  with records, once each. "Work hour records" / "labor hour records" could
  be rendered more naturally as "work log entries"; neither changes the unit.
- `rate_unspecified`: leaves the return-rate definition unresolved.
  `rate_count_defined`: explicitly retains return transaction count divided
  by all transaction count; the English is redundant but does not invert it.

No captured translation was edited or rerun. These judgments justify only a
separately labeled agent-reviewed sensitivity reading, not rewriting the
automatic score or supplying independent evidence of a real user's intent.
