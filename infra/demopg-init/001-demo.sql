-- Демо-данные для показа PG Control Center + ИИ.
-- Основная БД demo_shop (для мониторинга/диагностики/бэкапов) и пара
-- demo_prod / demo_test с разной структурой (для structure-sync и ИИ-плана).

-- ── demo_shop (создаётся как POSTGRES_DB) ──
CREATE TABLE customers (
  id serial PRIMARY KEY,
  email varchar(160) UNIQUE NOT NULL,
  full_name varchar(160),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id serial PRIMARY KEY,
  sku varchar(40) UNIQUE NOT NULL,
  title varchar(200) NOT NULL,
  price numeric(10, 2) NOT NULL DEFAULT 0
);

CREATE TABLE orders (
  id serial PRIMARY KEY,
  customer_id integer NOT NULL REFERENCES customers(id),
  product_id integer NOT NULL REFERENCES products(id),
  quantity integer NOT NULL DEFAULT 1,
  placed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_customer ON orders(customer_id);

INSERT INTO customers (email, full_name) VALUES
  ('alex@example.com', 'Alex Morgan'),
  ('blair@example.com', 'Blair Chen'),
  ('casey@example.com', 'Casey Jones');

INSERT INTO products (sku, title, price) VALUES
  ('SKU-1', 'Standard ticket', 49.90),
  ('SKU-2', 'VIP ticket', 149.00);

INSERT INTO orders (customer_id, product_id, quantity) VALUES
  (1, 1, 2), (2, 2, 1), (3, 1, 1);

CREATE VIEW recent_orders AS
  SELECT o.id, c.email, p.title, o.quantity, o.placed_at
  FROM orders o
  JOIN customers c ON c.id = o.customer_id
  JOIN products p ON p.id = o.product_id;

-- ── Пара БД для structure-sync (test→prod) ──
CREATE DATABASE demo_prod;
CREATE DATABASE demo_test;

\connect demo_prod
CREATE TABLE accounts (
  id serial PRIMARY KEY,
  email varchar(120),
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO accounts (email) VALUES ('one@example.com'), ('two@example.com');

CREATE FUNCTION account_label(acc_id integer) RETURNS text
  LANGUAGE sql AS $$ SELECT 'acct-' || acc_id $$;

\connect demo_test
-- Структура «новее»: добавлены колонка и таблица, изменена функция —
-- это и увидит structure-sync и объяснит ИИ-план.
CREATE TABLE accounts (
  id serial PRIMARY KEY,
  email varchar(120),
  phone varchar(40),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT accounts_email_unique UNIQUE (email)
);

CREATE TABLE audit_log (
  id serial PRIMARY KEY,
  action text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION account_label(acc_id integer) RETURNS text
  LANGUAGE sql AS $$ SELECT 'account #' || acc_id $$;
