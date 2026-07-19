CREATE DATABASE stagebridge_backend;
CREATE DATABASE stagebridge_prod;
CREATE DATABASE stagebridge_dev;
CREATE DATABASE stagebridge_stage;
CREATE DATABASE stagebridge_dryrun;
CREATE DATABASE stagebridge_live_prod;
CREATE DATABASE stagebridge_live_dev;
CREATE DATABASE stagebridge_live_stage;

\connect stagebridge_prod

CREATE TYPE public.order_status AS ENUM ('pending', 'paid', 'cancelled');

CREATE TABLE public.users (
  id serial PRIMARY KEY,
  email varchar(255),
  phone varchar(40)
);

CREATE TABLE public.customer (
  id integer PRIMARY KEY,
  full_name varchar(255)
);

CREATE TABLE public.orders (
  id serial PRIMARY KEY,
  customer_id integer,
  price varchar(32),
  status public.order_status NOT NULL DEFAULT 'pending'
);

CREATE INDEX idx_orders_customer_id ON public.orders(customer_id);

INSERT INTO public.users (id, email, phone) VALUES
  (1, 'alex@example.com', '+1-555-0101'),
  (2, 'blair@example.com', NULL),
  (3, 'casey@example.com', '+1-555-0103'),
  (4, 'alex@example.com', '+1-555-0199');

INSERT INTO public.customer (id, full_name) VALUES
  (10, 'Acme Events'),
  (11, 'Northwind Concerts'),
  (12, 'Bluebird Theater');

INSERT INTO public.orders (id, customer_id, price, status) VALUES
  (100, 10, '125.50', 'paid'),
  (101, 11, 'unknown', 'pending'),
  (102, 999, '42.00', 'paid'),
  (103, 12, '77.20', 'cancelled');

SELECT setval('public.users_id_seq', 4, true);
SELECT setval('public.orders_id_seq', 103, true);

\connect stagebridge_dev

CREATE TYPE public.order_status AS ENUM ('pending', 'paid', 'shipped', 'refunded');

CREATE TABLE public.users (
  id serial PRIMARY KEY,
  email varchar(255),
  phone varchar(40) NOT NULL,
  CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE TABLE public.customer (
  id integer PRIMARY KEY,
  display_name varchar(255) NOT NULL
);

CREATE TABLE public.orders (
  id serial PRIMARY KEY,
  customer_id integer,
  price numeric(10, 2),
  status public.order_status NOT NULL DEFAULT 'pending',
  CONSTRAINT orders_customer_id_fk FOREIGN KEY (customer_id) REFERENCES public.customer(id),
  CONSTRAINT orders_price_nonnegative CHECK (price >= 0)
);

CREATE INDEX idx_orders_customer_id ON public.orders(customer_id);

\connect stagebridge_stage

CREATE TYPE public.order_status AS ENUM ('pending', 'paid', 'shipped', 'refunded');

CREATE TABLE public.users (
  id serial PRIMARY KEY,
  email varchar(255) UNIQUE,
  phone varchar(40) NOT NULL
);

CREATE TABLE public.customer (
  id integer PRIMARY KEY,
  display_name varchar(255) NOT NULL
);

CREATE TABLE public.orders (
  id serial PRIMARY KEY,
  customer_id integer REFERENCES public.customer(id),
  price numeric(10, 2),
  status public.order_status NOT NULL DEFAULT 'pending'
);

\connect stagebridge_live_prod

CREATE SCHEMA inventory;
CREATE TYPE inventory.shipment_state AS ENUM ('queued', 'sent', 'cancelled');
CREATE SEQUENCE inventory.invoice_counter START 100 INCREMENT 1;

CREATE TABLE inventory.regions (
  id integer PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE inventory.accounts (
  id bigint PRIMARY KEY,
  email varchar(120),
  credit_limit text,
  age_text text,
  reference_code varchar(80),
  nickname text,
  full_name varchar(120),
  state inventory.shipment_state,
  region_id integer,
  code varchar(30) DEFAULT 'legacy'
);

CREATE TABLE inventory.legacy_events (
  id bigint PRIMARY KEY,
  payload text
);

CREATE INDEX accounts_region_lookup ON inventory.accounts(region_id);

INSERT INTO inventory.regions (id, name) VALUES (1, 'North'), (2, 'South');
INSERT INTO inventory.accounts (id, email, credit_limit, age_text, reference_code, nickname, full_name, state, region_id, code) VALUES
  (1, 'duplicate@example.com', '120.50', '42', 'ABCDEFGHIJKLMNO', NULL, 'Alex Morgan', 'sent', 1, 'legacy'),
  (2, 'duplicate@example.com', 'not-a-number', 'unknown', 'SHORT', 'Blair', 'Blair Chen', 'cancelled', 999, 'legacy'),
  (3, 'unique@example.com', '88.00', '31', 'ALSO-TOO-LONG', 'Casey', 'Casey Jones', 'queued', 2, 'legacy');

CREATE FUNCTION inventory.account_label(acc_id bigint) RETURNS text
  LANGUAGE sql AS $$ SELECT 'acct-' || acc_id $$;

CREATE VIEW inventory.sent_accounts AS
  SELECT id, email FROM inventory.accounts WHERE state = 'sent';

\connect stagebridge_live_dev

CREATE SCHEMA inventory;
CREATE TYPE inventory.shipment_state AS ENUM ('queued', 'sent', 'returned');
CREATE SEQUENCE inventory.invoice_counter START 100 INCREMENT 5;

CREATE TABLE inventory.regions (
  id integer PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE inventory.accounts (
  id bigint PRIMARY KEY,
  email varchar(120),
  credit_limit numeric(12, 2),
  age_text integer,
  reference_code varchar(12),
  nickname text NOT NULL,
  display_name varchar(120),
  state inventory.shipment_state,
  region_id integer,
  code varchar(30) DEFAULT 'current',
  required_tag text NOT NULL,
  CONSTRAINT accounts_email_unique UNIQUE (email),
  CONSTRAINT accounts_region_fk FOREIGN KEY (region_id) REFERENCES inventory.regions(id),
  CONSTRAINT accounts_credit_nonnegative CHECK (credit_limit >= 0)
);

CREATE TABLE inventory.shipment_batches (
  id bigint PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX accounts_region_lookup ON inventory.accounts(region_id, state);

CREATE FUNCTION inventory.account_label(acc_id bigint) RETURNS text
  LANGUAGE sql AS $$ SELECT 'account #' || acc_id $$;

CREATE VIEW inventory.sent_accounts AS
  SELECT id, email, display_name FROM inventory.accounts WHERE state = 'sent';

CREATE FUNCTION inventory.touch_updated() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$;

CREATE TRIGGER accounts_touch BEFORE UPDATE ON inventory.accounts
  FOR EACH ROW EXECUTE FUNCTION inventory.touch_updated();
