-- LearningOps v0.1: fresh, wholly fictional development fixture.
-- SQLite >= 3.37. All money is integer minor units; all instants use fixed UTC text.
-- No V1/V2 data, schema, reference SQL, or entity names were imported.
PRAGMA foreign_keys = ON;
CREATE TABLE centers (
  center_id TEXT PRIMARY KEY NOT NULL,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  region TEXT NOT NULL,
  business_timezone TEXT NOT NULL
) STRICT;
CREATE TABLE learners (
  learner_id TEXT PRIMARY KEY NOT NULL,
  display_name TEXT NOT NULL,
  member_since TEXT,
  email TEXT -- wholly fictional, deliberately restricted in the proposed policy
) STRICT;
CREATE TABLE courses (
  course_id TEXT PRIMARY KEY NOT NULL,
  code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  category TEXT
) STRICT;
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY NOT NULL,
  course_id TEXT NOT NULL REFERENCES courses(course_id),
  center_id TEXT NOT NULL REFERENCES centers(center_id),
  starts_at_utc TEXT NOT NULL,
  duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
  capacity_seats INTEGER CHECK(capacity_seats >= 0),
  UNIQUE(session_id, center_id)
) STRICT;
CREATE TABLE bookings (
  booking_id TEXT PRIMARY KEY NOT NULL,
  center_id TEXT NOT NULL REFERENCES centers(center_id),
  learner_id TEXT REFERENCES learners(learner_id),
  created_at_utc TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('confirmed','cancelled','draft')),
  currency TEXT NOT NULL CHECK(currency = 'TWD'),
  UNIQUE(booking_id, center_id)
) STRICT;
CREATE TABLE booking_items (
  item_id TEXT PRIMARY KEY NOT NULL,
  booking_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  center_id TEXT NOT NULL,
  seats INTEGER NOT NULL CHECK(seats > 0),
  unit_price_minor INTEGER NOT NULL CHECK(unit_price_minor >= 0),
  discount_minor INTEGER NOT NULL CHECK(discount_minor >= 0),
  CHECK(discount_minor <= seats * unit_price_minor),
  FOREIGN KEY(booking_id, center_id) REFERENCES bookings(booking_id, center_id),
  FOREIGN KEY(session_id, center_id) REFERENCES sessions(session_id, center_id)
) STRICT;
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY NOT NULL,
  booking_id TEXT NOT NULL REFERENCES bookings(booking_id),
  posted_at_utc TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('succeeded','pending','failed')),
  amount_minor INTEGER NOT NULL CHECK(amount_minor > 0)
) STRICT;
CREATE TABLE refunds (
  refund_id TEXT PRIMARY KEY NOT NULL,
  item_id TEXT NOT NULL REFERENCES booking_items(item_id),
  posted_at_utc TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('succeeded','pending','failed')),
  amount_minor INTEGER NOT NULL CHECK(amount_minor > 0)
) STRICT;
CREATE TABLE attendance (
  attendance_id TEXT PRIMARY KEY NOT NULL,
  item_id TEXT NOT NULL REFERENCES booking_items(item_id),
  attendee_code TEXT NOT NULL,
  checked_in_at_utc TEXT NOT NULL,
  UNIQUE(item_id, attendee_code)
) STRICT;
CREATE TABLE monthly_targets (
  center_id TEXT NOT NULL REFERENCES centers(center_id),
  month_start_local TEXT NOT NULL,
  metric_id TEXT NOT NULL CHECK(metric_id = 'confirmed_booked_amount'),
  target_minor INTEGER NOT NULL CHECK(target_minor >= 0),
  PRIMARY KEY(center_id, month_start_local, metric_id)
) STRICT;
CREATE INDEX bookings_time_idx ON bookings(created_at_utc);
CREATE INDEX bookings_center_idx ON bookings(center_id);
CREATE INDEX items_booking_idx ON booking_items(booking_id);
CREATE INDEX items_session_idx ON booking_items(session_id);
CREATE INDEX payments_booking_idx ON payments(booking_id);
CREATE INDEX refunds_item_idx ON refunds(item_id);
