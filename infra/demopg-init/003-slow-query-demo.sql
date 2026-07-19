-- Реалистичная нагрузка для Monitoring -> Slow queries и AI Query Advisor.
-- Таблицы намеренно имеют только PK: поля фильтрации и JOIN не индексированы.

CREATE TABLE IF NOT EXISTS demo_perf_customers (
  id bigint PRIMARY KEY,
  email text NOT NULL,
  segment text NOT NULL,
  created_at timestamptz NOT NULL
);

INSERT INTO demo_perf_customers (id, email, segment, created_at)
SELECT
  n,
  'customer-' || n || '@example.test',
  (ARRAY['startup', 'business', 'enterprise'])[1 + n % 3],
  now() - ((n % 730) || ' days')::interval
FROM generate_series(1, 40000) AS seed(n)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS demo_perf_orders (
  id bigint PRIMARY KEY,
  external_ref text NOT NULL,
  customer_id bigint NOT NULL,
  region text NOT NULL,
  status text NOT NULL,
  total_amount numeric(12, 2) NOT NULL,
  created_at timestamptz NOT NULL
);

INSERT INTO demo_perf_orders (
  id, external_ref, customer_id, region, status, total_amount, created_at
)
SELECT
  n,
  'ORDER-' || n,
  1 + (n * 37) % 40000,
  (ARRAY['KZ-SOUTH', 'KZ-NORTH', 'EU-WEST', 'US-EAST'])[1 + n % 4],
  (ARRAY['new', 'processing', 'shipped', 'failed'])[1 + n % 4],
  round((25 + (n % 20000) / 17.0)::numeric, 2),
  now() - ((n % 365) || ' days')::interval
FROM generate_series(1, 180000) AS seed(n)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS demo_perf_order_events (
  id bigint PRIMARY KEY,
  order_ref text NOT NULL,
  event_type text NOT NULL,
  latency_ms integer NOT NULL,
  occurred_at timestamptz NOT NULL
);

INSERT INTO demo_perf_order_events (
  id, order_ref, event_type, latency_ms, occurred_at
)
SELECT
  n,
  'ORDER-' || (1 + (n * 53) % 180000),
  (ARRAY['accepted', 'charged', 'packed', 'dispatched'])[1 + n % 4],
  10 + n % 2500,
  now() - ((n % 90) || ' days')::interval
FROM generate_series(1, 360000) AS seed(n)
ON CONFLICT (id) DO NOTHING;

ANALYZE demo_perf_customers;
ANALYZE demo_perf_orders;
ANALYZE demo_perf_order_events;

-- Очищаем статистику загрузки и оставляем только полезные demo-запросы.
SELECT pg_stat_statements_reset();

\o /dev/null

SELECT region, status, count(*) AS orders, avg(total_amount) AS avg_total
FROM demo_perf_orders
GROUP BY region, status
ORDER BY avg(total_amount) DESC;
SELECT region, status, count(*) AS orders, avg(total_amount) AS avg_total
FROM demo_perf_orders
GROUP BY region, status
ORDER BY avg(total_amount) DESC;
SELECT region, status, count(*) AS orders, avg(total_amount) AS avg_total
FROM demo_perf_orders
GROUP BY region, status
ORDER BY avg(total_amount) DESC;

SELECT c.segment, count(*) AS orders, avg(o.total_amount) AS avg_total
FROM demo_perf_customers c
JOIN demo_perf_orders o ON o.customer_id = c.id
GROUP BY c.segment
ORDER BY count(*) DESC;
SELECT c.segment, count(*) AS orders, avg(o.total_amount) AS avg_total
FROM demo_perf_customers c
JOIN demo_perf_orders o ON o.customer_id = c.id
GROUP BY c.segment
ORDER BY count(*) DESC;
SELECT c.segment, count(*) AS orders, avg(o.total_amount) AS avg_total
FROM demo_perf_customers c
JOIN demo_perf_orders o ON o.customer_id = c.id
GROUP BY c.segment
ORDER BY count(*) DESC;

SELECT o.region, count(*) AS events, avg(e.latency_ms) AS avg_latency_ms
FROM demo_perf_orders o
JOIN demo_perf_order_events e ON e.order_ref = o.external_ref
GROUP BY o.region
ORDER BY avg(e.latency_ms) DESC;
SELECT o.region, count(*) AS events, avg(e.latency_ms) AS avg_latency_ms
FROM demo_perf_orders o
JOIN demo_perf_order_events e ON e.order_ref = o.external_ref
GROUP BY o.region
ORDER BY avg(e.latency_ms) DESC;
SELECT o.region, count(*) AS events, avg(e.latency_ms) AS avg_latency_ms
FROM demo_perf_orders o
JOIN demo_perf_order_events e ON e.order_ref = o.external_ref
GROUP BY o.region
ORDER BY avg(e.latency_ms) DESC;

SELECT count(*) AS matching_orders, max(created_at) AS latest_order
FROM demo_perf_orders
WHERE customer_id BETWEEN 5000 AND 9000
  AND status IN ('processing', 'failed');
SELECT count(*) AS matching_orders, max(created_at) AS latest_order
FROM demo_perf_orders
WHERE customer_id BETWEEN 5000 AND 9000
  AND status IN ('processing', 'failed');
SELECT count(*) AS matching_orders, max(created_at) AS latest_order
FROM demo_perf_orders
WHERE customer_id BETWEEN 5000 AND 9000
  AND status IN ('processing', 'failed');

\o
