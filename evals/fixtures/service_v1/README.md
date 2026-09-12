# Service operations fixture v1

Entirely fictional, no personal or customer data. Six tables; natural-key
foreign keys deliberately do not reference parent numeric IDs. A work log
is not a ticket and an event is not a work log. `team_links` deliberately
offers two ambiguous paths to teams. There is no declared orphan FK.

Setup is new-database-only: create `grepbit_spike_service` separately, then
apply schema.sql and seed.sql in that database. Never DROP or reseed an
existing database. Grant only CONNECT, public USAGE and table SELECT to the
existing `grepbit_ro`. Admin credentials must never be written here or passed
to application code. The runtime DSN variable is `GREPBIT_SERVICE_DSN`.

`overlay.json` opts in only explicitly fictional team/project labels for
grounding; it defines no reviewed metric, segment or absent business concept.
No new production business overlay has been approved by the owner.

Fixed checks: teams=3, projects=4, tickets=8, work_logs=10, ticket_events=9,
team_links=2. Logged minutes total=499 versus estimates=469. Calendar logged
minutes Jan/Feb/Mar=100/50/250; unknown-date minutes=99. North team has no
February work, so March growth is NULL; South has February=50/March=100,
so growth is 1.0. Thresholding teams to totals >200 must retain North's
share 349/499, not 100%. Equal work timestamps and zero/NULL minutes are
deliberate. Business timezone is Asia/Taipei; as_of is 2026-04-15 noon.

`evals/cases/tier0/service.yaml` is authored smoke coverage, not a blind
holdout. The default no-overlay run measures schema understanding; adding
this public-label overlay isolates value grounding. Neither measures A4's
large-schema benefit. Differential and golden checks precede live questions.
