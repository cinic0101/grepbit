# retail_v1 owner-approved fixture

This is the deterministic, owner-approved, immutable v1 business oracle for
G0. Facts or policy changes require a new fixture revision. It is not a runtime
database setup and it is not a claim of Wren syntax or runtime compatibility;
G1 must independently establish semantic-engine syntax and runtime behavior.

The fixture uses the Asia/Taipei business timezone and TWD. A July 2026 order
period is the half-open interval from `2026-07-01T00:00:00+08:00` up to, but not
including, `2026-08-01T00:00:00+08:00`. Recognized revenue means completed-order
gross amount minus a NULL-as-zero discount; it excludes tax, returns, and
cancelled orders. `net_after_returns` subtracts returns for completed orders in
the requested **order** period, even if the return event is recorded later.
The monthly-target relation has a composite `(customer_id, month_start)` key;
using only `customer_id` is an incomplete grain assertion.

## Approved business decisions

- TWD, the Asia/Taipei calendar, the selected order time field, and the fixed
  `as_of` instant are approved.
- Revenue excludes tax and returns; return attribution uses order-period
  membership rather than return-event date.
- `NULL` discount is zero for this fixture.
- Cancellation treatment, recognized-revenue entity grain, and the listed
  relationship cardinalities are approved.
- Rankings include zero-revenue customers with the stated stable tie-breaker.
- Zero and NULL target denominators produce no ratio.
- Sensitivity/redaction classifications and the `[REDACTED]` display marker are
  approved.
- The unsafe-function and malicious-comment threat probes are approved.

These approvals apply only to this immutable fixture revision. They do not
approve unreviewed source metadata or any production semantic-model mutation.
