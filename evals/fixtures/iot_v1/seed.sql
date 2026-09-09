INSERT INTO sites (site_id, site_name, region) VALUES
    ('s01', 'Taipei HQ', 'north'),
    ('s02', 'Taichung Plant', 'central'),
    ('s03', 'Kaohsiung Depot', 'south');

INSERT INTO devices (device_id, site_id, model, firmware, status, installed_on, monthly_fee) VALUES
    ('d001', 's01', 'AP-500', '2.1.0', 'online',      '2026-01-10', 300.00),
    ('d002', 's01', 'AP-500', '2.0.3', 'offline',     '2026-02-14', 300.00),
    ('d003', 's01', 'SW-24',  '1.9.0', 'online',      '2026-03-01', 500.00),
    ('d004', 's02', 'AP-500', '2.1.0', 'online',      '2026-03-15', 300.00),
    ('d005', 's02', 'GW-10',  '3.0.1', 'maintenance', '2026-04-02', 800.00),
    ('d006', 's03', 'AP-300', '1.4.2', 'online',      '2026-05-20', 200.00),
    ('d007', 's03', 'AP-300', '1.4.2', 'offline',     '2026-06-01', 200.00),
    ('d008', 's03', 'SW-24',  '1.9.0', 'online',      '2026-06-18', 500.00);

INSERT INTO alerts (alert_id, device_id, severity, category, raised_at, resolved_at, downtime_minutes) VALUES
    (1,  'd001', 'warning',  'latency',     '2026-07-02 09:00+08', '2026-07-02 09:30+08', NULL),
    (2,  'd002', 'critical', 'disconnect',  '2026-07-03 22:10+08', '2026-07-04 01:40+08', 210),
    (3,  'd002', 'critical', 'disconnect',  '2026-07-15 03:00+08', '2026-07-15 04:00+08', 60),
    (4,  'd003', 'info',     'firmware',    '2026-07-05 10:00+08', '2026-07-05 10:05+08', NULL),
    (5,  'd004', 'warning',  'latency',     '2026-07-08 14:20+08', '2026-07-08 14:50+08', NULL),
    (6,  'd005', 'critical', 'power',       '2026-07-11 06:00+08', '2026-07-11 12:00+08', 360),
    (7,  'd005', 'warning',  'temperature', '2026-07-19 15:00+08', NULL,                  NULL),
    (8,  'd006', 'info',     'firmware',    '2026-07-21 08:00+08', '2026-07-21 08:02+08', NULL),
    (9,  'd007', 'critical', 'disconnect',  '2026-07-25 23:30+08', '2026-07-26 02:30+08', 180),
    (10, 'd007', 'critical', 'disconnect',  '2026-07-31 23:59+08', '2026-08-01 00:20+08', 21),
    (11, 'd001', 'warning',  'latency',     '2026-08-01 00:00+08', '2026-08-01 00:10+08', NULL),
    (12, 'd004', 'critical', 'power',       '2026-08-05 07:00+08', '2026-08-05 08:30+08', 90),
    (13, 'd008', 'info',     'firmware',    '2026-08-09 11:00+08', '2026-08-09 11:01+08', NULL),
    (14, 'd002', 'critical', 'disconnect',  '2026-08-12 02:00+08', '2026-08-12 03:00+08', 60),
    (15, 'd006', 'warning',  'temperature', '2026-08-14 16:00+08', '2026-08-14 16:45+08', NULL);

INSERT INTO readings (reading_id, device_id, measured_at, temperature_c, uptime_pct, throughput_mbps)
SELECT
    row_number() OVER (),
    d.device_id,
    ts,
    38.0 + (extract(hour from ts)::int % 7) + CASE WHEN d.device_id IN ('d005', 'd007') THEN 6.5 ELSE 0 END,
    CASE WHEN d.status = 'offline' THEN 62.50 WHEN d.status = 'maintenance' THEN 80.00 ELSE 99.50 END,
    CASE d.model WHEN 'SW-24' THEN 900.00 WHEN 'GW-10' THEN 450.00 WHEN 'AP-500' THEN 300.00 ELSE 150.00 END
        + (extract(hour from ts)::int % 5) * 10
FROM devices d
CROSS JOIN generate_series('2026-07-01 00:00+08'::timestamptz, '2026-08-14 23:00+08'::timestamptz, interval '6 hours') AS ts;
