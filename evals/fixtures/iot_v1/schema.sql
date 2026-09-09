-- Synthetic IoT operations schema for the tier-0 generalization spike.
-- Deliberately different vocabulary and shapes from retail_v1.
CREATE TABLE sites (
    site_id TEXT PRIMARY KEY,
    site_name TEXT NOT NULL,
    region TEXT NOT NULL,
    tz TEXT NOT NULL DEFAULT 'Asia/Taipei'
);
COMMENT ON TABLE sites IS 'Customer premises where devices are installed.';
COMMENT ON COLUMN sites.region IS 'Sales region code: north, central, south.';

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL REFERENCES sites(site_id),
    model TEXT NOT NULL,
    firmware TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('online', 'offline', 'maintenance')),
    installed_on DATE NOT NULL,
    monthly_fee NUMERIC(10, 2) NOT NULL
);
COMMENT ON COLUMN devices.status IS 'Current connectivity state reported by the gateway.';
COMMENT ON COLUMN devices.monthly_fee IS 'Subscription fee in TWD billed per device per month.';

CREATE TABLE alerts (
    alert_id BIGINT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    category TEXT NOT NULL,
    raised_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    downtime_minutes INTEGER
);
COMMENT ON TABLE alerts IS 'One row per alert raised by a device.';
COMMENT ON COLUMN alerts.downtime_minutes IS 'Minutes the device was unreachable; NULL when the alert caused no downtime.';

CREATE TABLE readings (
    reading_id BIGINT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    measured_at TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(5, 2) NOT NULL,
    uptime_pct NUMERIC(5, 2) NOT NULL,
    throughput_mbps NUMERIC(8, 2) NOT NULL
);
COMMENT ON TABLE readings IS 'Hourly telemetry samples per device.';
