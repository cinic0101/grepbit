# Comparable products: advertised query features and our probe results

Surveyed on 2026-09-08 from vendor documentation and announcements: Snowflake
Cortex Analyst, Databricks AI/BI Genie, ThoughtSpot Spotter, Amazon Q in
QuickSight, Google Looker Conversational Analytics, Power BI Copilot, Wren AI.
Probe set: `evals/cases/tier0/pos_features.yaml` (32 cases) with the overlay on
`text2sql_test`; suggestions via `evals/spike_suggest.py`. Results in
`evidence/spike-tier0/pos-features-02.json` and `pos-suggested-02.json`.

| Feature | Advertised by | Ours | Probe result |
|---|---|---|---|
| Natural-language question over a governed semantic model | all seven | tier-0 plus overlay | 78 base cases; 14/14 overlay set |
| Multi-turn follow-ups (change period, add filter, breakdown, limit, new topic) | Cortex Analyst, Genie, ThoughtSpot, Looker CA API, Power BI Copilot | previous-turn context | 6/6 follow-ups, 1/1 new topic ignored context |
| Suggested questions the system can then answer | Genie, Cortex Analyst, QuickSight | schema-driven suggestions | 10 proposed, 9 answered, 1 refused (impossible suggestion) |
| Verified queries / trusted assets / question-SQL pairs | Cortex Analyst, Genie, Looker, Wren AI | reviewed metrics as plan fragments | 14/14, 8 verified |
| Show SQL and explain the derivation | Genie, Looker, ThoughtSpot | SQL, lineage, interpretation, assumptions | every answer |
| Time intelligence (period comparison, last N days, quarter, YTD, weekly and quarterly trends, same month last year) | QuickSight Q, ThoughtSpot, all | day, week, month, quarter, year units and grains | 8/8 |
| Top-N, bottom-N, named-entity comparison | all | order, limit, IN filters | 3/3 |
| Several measures in one answer | all | up to 4 on one base table | same base 1/1; cross-base refused honestly |
| Numeric, enum, null filters, time on a parent table | all | typed filters | 3/3 |
| Ratios, share of total, growth rate | QuickSight Q, ThoughtSpot, Cortex Analyst, Looker | not in the algebra | growth refused; share by payment method answered as plain sums (gap) |
| Forecast, "why did it change" | QuickSight Q, ThoughtSpot | out of scope (Genie, Looker, Cortex also decline) | refused |
| Charts and narrative | Genie, Looker, Power BI, QuickSight, Wren AI | parent agent's job | n/a |
| Feedback and review loop | Genie, Wren AI, Cortex Analyst | ask log and overlay; no review UI | not built |
| Row-level security | all | read-only role only | not built |

Gap that matters: derived metrics, and the fact that a missing shape is
answered as a narrower question. Everything else advertised as a query feature
is present or deliberately delegated to the calling agent.

## How the field handles first-seen terms

Nobody solves it with cleverness; the pattern is three-fold. Closed vocabulary
with synonyms (semantic views, LookML, Cortex synonyms, Genie instructions);
unmatched tokens surfaced to the user (ThoughtSpot binds search tokens to
columns and flags the unrecognized ones); a curation loop from question logs
(Genie review requests, Cortex verified queries, Wren question-SQL pairs).
Pure retrieval text-to-SQL drifts to the nearest example and has the highest
wrong-answer risk. Our design follows the same three moves: overlay
vocabulary, clarify with a pending plan on unmatched concepts, review queue.

## Sources

- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/analyst-optimization
- https://docs.databricks.com/aws/en/genie-agents/talk-to-genie
- https://learn.microsoft.com/en-us/azure/databricks/genie/trusted-assets
- https://www.databricks.com/blog/aibi-genie-now-generally-available
- https://www.thoughtspot.com/blog/introducing-spotter-ai-analyst
- https://www.thoughtspot.com/product/agents/spotter
- https://aws.amazon.com/blogs/business-intelligence/new-analytical-questions-available-in-amazon-quicksight-q-why-and-forecast/
- https://aws.amazon.com/blogs/aws/amazon-quicksight-q-to-answer-ad-hoc-business-questions/
- https://docs.cloud.google.com/looker/docs/conversational-analytics-overview
- https://cloud.google.com/blog/products/data-analytics/understanding-lookers-conversational-analytics-api
- https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-ask-data-question
- https://powerbi.microsoft.com/en-us/blog/deprecating-power-bi-qa/
- https://www.getwren.ai/oss
- https://github.com/Canner/WrenAI/blob/main/README.md
