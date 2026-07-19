from app.models.server import Server
from app.services.pg_connection import execute_on_server


async def run_diagnostics(server: Server) -> dict:
    checks = []
    warnings = 0

    for role in ("main", "app_users", "app_service"):
        rows = await execute_on_server(server, f"select 1 from pg_roles where rolname = '{role}'")
        if rows:
            checks.append({"name": f"Роль {role}", "status": "ok", "details": "существует"})
        else:
            checks.append({"name": f"Роль {role}", "status": "warning", "details": "НЕ существует"})
            warnings += 1

    db_rows = await execute_on_server(
        server,
        "select datname, datacl::text from pg_database "
        "where datname not in ('template0', 'template1', 'postgres') and datallowconn"
    )
    for db in db_rows:
        acl = db.get("datacl") or ""
        checks.append({
            "name": f"ACL {db['datname']}",
            "status": "ok",
            "details": acl,
        })

    connectable_dbs = [db["datname"] for db in db_rows]
    for db_name in connectable_dbs:
        try:
            triggers = await execute_on_server(
                server, "select evtname, evtenabled from pg_event_trigger", db_name
            )
            if triggers:
                names = ", ".join(f"{t['evtname']}({t['evtenabled']})" for t in triggers)
                checks.append({"name": f"Event triggers ({db_name})", "status": "ok", "details": names})
            else:
                checks.append({"name": f"Event triggers ({db_name})", "status": "info", "details": "нет"})
        except Exception:
            checks.append({"name": f"Event triggers ({db_name})", "status": "warning", "details": "не удалось подключиться"})
            warnings += 1

    for db_name in connectable_dbs:
        try:
            has_connect = await execute_on_server(
                server,
                f"select has_database_privilege('app_service', '{db_name}', 'CONNECT') as ok"
            )
            if has_connect and has_connect[0].get("ok"):
                total = await execute_on_server(
                    server,
                    "select count(*) as cnt from pg_tables "
                    "where schemaname not in ('pg_catalog','information_schema')",
                    db_name,
                )
                granted = await execute_on_server(
                    server,
                    "select count(*) as cnt from information_schema.role_table_grants "
                    "where grantee = 'app_service' and privilege_type = 'SELECT'",
                    db_name,
                )
                t = total[0]["cnt"] if total else 0
                g = granted[0]["cnt"] if granted else 0
                if t == 0:
                    checks.append({"name": f"DML app_service ({db_name})", "status": "ok", "details": "нет таблиц"})
                elif t == g:
                    checks.append({"name": f"DML app_service ({db_name})", "status": "ok", "details": f"{g}/{t}"})
                else:
                    checks.append({"name": f"DML app_service ({db_name})", "status": "warning", "details": f"{g}/{t}"})
                    warnings += 1
        except Exception:
            pass

    return {
        "server_name": server.name,
        "checks": checks,
        "warnings": warnings,
        "ok": len(checks) - warnings,
    }
