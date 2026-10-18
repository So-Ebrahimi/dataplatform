CREATE TABLE IF NOT EXISTS public.sales (
    sale_id INTEGER PRIMARY KEY,
    sale_date DATE NOT NULL,
    region VARCHAR(40) NOT NULL,
    product VARCHAR(80) NOT NULL,
    category VARCHAR(40) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL
);

INSERT INTO public.sales (sale_id, sale_date, region, product, category, quantity, unit_price)
VALUES
 (1, '2026-01-05', 'North', 'Laptop Pro', 'Electronics', 2, 1299.00),
 (2, '2026-01-07', 'South', 'Desk Chair', 'Furniture', 5, 189.50),
 (3, '2026-01-11', 'East', 'Monitor 27', 'Electronics', 3, 329.00),
 (4, '2026-01-13', 'West', 'Standing Desk', 'Furniture', 1, 549.00),
 (5, '2026-02-02', 'North', 'Keyboard', 'Accessories', 8, 79.00),
 (6, '2026-02-04', 'South', 'Laptop Pro', 'Electronics', 1, 1299.00),
 (7, '2026-02-09', 'East', 'Desk Chair', 'Furniture', 4, 189.50),
 (8, '2026-02-12', 'West', 'Monitor 27', 'Electronics', 6, 329.00),
 (9, '2026-03-01', 'North', 'Standing Desk', 'Furniture', 2, 549.00),
 (10, '2026-03-03', 'South', 'Keyboard', 'Accessories', 10, 79.00),
 (11, '2026-03-14', 'East', 'Laptop Pro', 'Electronics', 2, 1299.00),
 (12, '2026-03-21', 'West', 'Desk Chair', 'Furniture', 3, 189.50)
ON CONFLICT (sale_id) DO NOTHING;

-- In a real deployment, use a dedicated source database user with SELECT-only grants.
