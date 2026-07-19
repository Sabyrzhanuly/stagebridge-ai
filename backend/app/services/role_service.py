import secrets
import string

from app.models.server import Server
from app.services.pg_connection import execute_on_server, execute_command, quote_ident


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def list_roles(server: Server) -> list[dict]:
    sql = """
    select r.rolname,
      r.rolcanlogin,
      r.rolsuper,
      r.rolinherit,
      r.rolcreatedb,
      r.rolcreaterole,
      r.rolconnlimit,
      coalesce(
        array_agg(g.rolname order by g.rolname)
          filter (where g.rolname is not null),
        '{}'
      ) as member_of
    from pg_roles r
      left join pg_auth_members am on am.member = r.oid
      left join pg_roles g on g.oid = am.roleid
    where r.rolname not like 'pg_%'
    group by r.rolname, r.rolcanlogin, r.rolsuper,
             r.rolinherit, r.rolcreatedb, r.rolcreaterole, r.rolconnlimit
    order by r.rolname
    """
    return await execute_on_server(server, sql)


async def create_user(server: Server, username: str, password: str | None, group: str) -> str:
    if not password:
        password = generate_password()
    safe_pw = password.replace("'", "''")
    u, g = quote_ident(username), quote_ident(group)
    await execute_command(server, f"create role {u} login password '{safe_pw}'")
    await execute_command(server, f"grant {g} to {u}")
    if group == "main":
        await execute_command(server, f"grant app_users to {u}")
    return password


async def create_service_account(
    server: Server, username: str, password: str | None, database: str
) -> str:
    if not password:
        password = generate_password()
    safe_pw = password.replace("'", "''")
    u, db = quote_ident(username), quote_ident(database)

    rows = await execute_on_server(server, "select 1 from pg_roles where rolname = $1", "postgres", username)
    if not rows:
        await execute_command(server, f"create role {u} login password '{safe_pw}'")
    await execute_command(server, f"grant app_service to {u}")
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
        execute format('grant execute on all functions in schema %%I to app_service', rec_.schema_name);
      end loop;
    end$$;
    """
    await execute_command(server, grant_sql, database)

    owner_rows = await execute_on_server(
        server,
        "select pg_catalog.pg_get_userbyid(datdba) as owner from pg_database where datname = $1",
        "postgres", database,
    )
    owner = quote_ident(owner_rows[0]["owner"].strip() if owner_rows else "main")

    default_privs = f"""
    alter default privileges for role {owner} in schema public
      grant select, insert, update, delete on tables to app_service;
    alter default privileges for role {owner} in schema public
      grant usage, select on sequences to app_service;
    """
    await execute_command(server, default_privs, database)

    return password


async def grant_role(server: Server, username: str, group: str) -> None:
    await execute_command(server, f"grant {quote_ident(group)} to {quote_ident(username)}")


async def revoke_role(server: Server, username: str, group: str) -> None:
    await execute_command(server, f"revoke {quote_ident(group)} from {quote_ident(username)}")


async def drop_role(server: Server, username: str) -> None:
    await execute_command(server, f"drop role if exists {quote_ident(username)}")
