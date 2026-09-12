-- Synthetic-only service fixture. Run only in a NEW isolated database.
BEGIN;
CREATE TABLE teams (
    id integer PRIMARY KEY,
    team_code text NOT NULL UNIQUE,
    team_name text NOT NULL
);
CREATE TABLE projects (
    id integer PRIMARY KEY,
    project_key text NOT NULL UNIQUE,
    project_name text NOT NULL,
    team_code text NOT NULL REFERENCES teams(team_code)
);
CREATE TABLE tickets (
    id integer PRIMARY KEY,
    project_key text NOT NULL REFERENCES projects(project_key),
    status text NOT NULL,
    created_at timestamptz,
    closed_at timestamptz,
    estimate_minutes numeric
);
CREATE TABLE work_logs (
    id integer PRIMARY KEY,
    ticket_id integer NOT NULL REFERENCES tickets(id),
    logged_at timestamptz,
    minutes numeric
);
CREATE TABLE ticket_events (
    id integer PRIMARY KEY,
    ticket_id integer NOT NULL REFERENCES tickets(id),
    occurred_at timestamptz,
    event_type text NOT NULL
);
CREATE TABLE team_links (
    id integer PRIMARY KEY,
    source_team text NOT NULL REFERENCES teams(team_code),
    target_team text NOT NULL REFERENCES teams(team_code)
);
COMMENT ON TABLE work_logs IS 'One work entry, not one ticket; minutes are logged work, not estimates.';
COMMENT ON COLUMN tickets.closed_at IS 'NULL means not known closed; different from ticket creation time.';
COMMENT ON COLUMN work_logs.logged_at IS 'NULL means unknown work date, not a zero-minute period.';
COMMIT;
