INSERT INTO customers (customer_id, display_name, email, region) VALUES
    ('c001', 'Ada', 'ada@example.test', 'north'),
    ('c002', 'Ben', 'ben@example.test', 'south'),
    ('c003', 'Chen', 'chen@example.test', NULL),
    ('c004', 'Dee', 'dee@example.test', 'north');

INSERT INTO orders (
    order_id, customer_id, ordered_at, status, gross_amount, discount_amount, tax_amount
) VALUES
    ('o1001', 'c001', '2026-07-01 00:00:00+08', 'completed', 100.00, 10.00, 5.00),
    ('o1002', 'c002', '2026-07-31 23:59:59+08', 'completed', 200.00, 0.00, 10.00),
    ('o1003', 'c001', '2026-08-01 00:00:00+08', 'completed', 300.00, 30.00, 15.00),
    ('o1004', 'c003', '2026-07-15 12:00:00+08', 'cancelled', 50.00, 0.00, 3.00),
    ('o1005', 'c003', '2026-07-20 09:00:00+08', 'completed', 0.00, NULL, NULL);

INSERT INTO order_lines (order_id, line_id, product_sku, line_amount) VALUES
    ('o1001', 1, 'widget-a', 60.00),
    ('o1001', 2, 'widget-b', 40.00),
    ('o1002', 1, 'widget-a', 200.00),
    ('o1003', 1, 'widget-c', 300.00),
    ('o1004', 1, 'widget-b', 50.00),
    ('o1005', 1, 'widget-free', 0.00);

INSERT INTO returns (return_id, order_id, returned_at, return_amount) VALUES
    ('r1001', 'o1001', '2026-07-03 12:00:00+08', 10.00),
    ('r1002', 'o1001', '2026-07-05 09:00:00+08', 5.00),
    ('r1003', 'o1002', '2026-08-02 12:00:00+08', 50.00);

INSERT INTO customer_monthly_targets (customer_id, month_start, target_amount) VALUES
    ('c001', '2026-07-01', 100.00),
    ('c002', '2026-07-01', 0.00),
    ('c003', '2026-07-01', 100.00),
    ('c004', '2026-07-01', NULL);
