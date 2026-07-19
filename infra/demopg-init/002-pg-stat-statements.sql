-- Включаем pg_stat_statements для мониторинга медленных запросов и AI Query Advisor.
-- shared_preload_libraries задаётся в docker-compose (command); здесь создаём расширение.
\connect postgres
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\connect demo_shop
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
