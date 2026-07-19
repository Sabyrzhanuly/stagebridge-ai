from app.models.server import Server
from app.services.pg_connection import execute_on_server, execute_command, quote_ident


async def list_databases(server: Server) -> list[dict]:
    sql = """
    select d.datname,
      pg_catalog.pg_get_userbyid(d.datdba) as owner,
      pg_catalog.pg_size_pretty(pg_catalog.pg_database_size(d.datname)) as size,
      pg_catalog.pg_database_size(d.datname) as size_bytes,
      d.datacl::text as datacl,
      pg_catalog.pg_encoding_to_char(d.encoding) as encoding
    from pg_database d
    where d.datname not in ('template0')
    order by d.datname
    """
    return await execute_on_server(server, sql)


async def create_database(server: Server, name: str, mode: str, with_service: bool) -> None:
    db = quote_ident(name)
    if mode == "shared":
        await execute_command(server, f"create database {db} owner main template template_app")
        await execute_command(server, f"revoke connect on database {db} from public")
        await execute_command(server, f"grant connect, create on database {db} to app_users")
        await execute_command(server, f"grant connect on database {db} to app_service")
    else:
        await execute_command(server, f"create database {db} owner main")
        await execute_command(server, f"revoke connect on database {db} from public")
        if with_service:
            await execute_command(server, f"grant connect on database {db} to app_service")
            grant_sql = """
            do $$
            declare
              rec_ record;
            begin
              for rec_ in
                select schema_name from information_schema.schemata
                where schema_name not in ('pg_catalog', 'information_schema')
                  and schema_name not like 'pg_temp%%'
                  and schema_name not like 'pg_toast%%'
              loop
                execute format('grant usage on schema %%I to app_service', rec_.schema_name);
                execute format('grant select, insert, update, delete on all tables in schema %%I to app_service', rec_.schema_name);
                execute format('grant usage, select on all sequences in schema %%I to app_service', rec_.schema_name);
              end loop;
            end$$;
            """
            await execute_command(server, grant_sql, name)
            await execute_command(
                server,
                "alter default privileges for role main in schema public "
                "grant select, insert, update, delete on tables to app_service",
                name,
            )


async def drop_database(server: Server, name: str) -> None:
    await execute_command(server, f"drop database if exists {quote_ident(name)}")


async def list_schemas(server: Server, database: str) -> list[dict]:
    sql = """
    select n.nspname as schema_name,
      pg_catalog.pg_get_userbyid(n.nspowner) as owner
    from pg_namespace n
    where n.nspname not in ('pg_catalog', 'information_schema', 'pg_toast')
      and n.nspname not like 'pg_temp%%'
      and n.nspname not like 'pg_toast_temp%%'
    order by n.nspname
    """
    return await execute_on_server(server, sql, database)


async def list_tables(server: Server, database: str) -> list[dict]:
    sql = """
    select t.schemaname as schema_name,
      t.tablename as table_name,
      t.tableowner as owner,
      c.reltuples::bigint as row_estimate,
      pg_size_pretty(pg_total_relation_size(c.oid)) as size
    from pg_tables t
      join pg_class c on c.relname = t.tablename
      join pg_namespace n on n.oid = c.relnamespace and n.nspname = t.schemaname
    where t.schemaname not in ('pg_catalog', 'information_schema')
    order by t.schemaname, t.tablename
    """
    return await execute_on_server(server, sql, database)


async def list_event_triggers(server: Server, database: str) -> list[dict]:
    sql = """
    select e.evtname as name,
      e.evtenabled as enabled,
      p.proname as function_name
    from pg_event_trigger e
      join pg_proc p on p.oid = e.evtfoid
    order by e.evtname
    """
    return await execute_on_server(server, sql, database)


async def list_tables_size(server: Server, database: str) -> list[dict]:
    sql = """
    select
      t.schemaname as schema,
      t.relname as tablename,
      pg_total_relation_size(t.relid) as total_bytes,
      pg_size_pretty(pg_total_relation_size(t.relid)) as total_size,
      pg_size_pretty(pg_relation_size(t.relid)) as data_size,
      pg_size_pretty(
        pg_total_relation_size(t.relid) - pg_relation_size(t.relid)
      ) as index_size,
      coalesce(t.n_live_tup, 0) as row_estimate
    from pg_stat_user_tables t
    order by pg_total_relation_size(t.relid) desc
    """
    return await execute_on_server(server, sql, database)
