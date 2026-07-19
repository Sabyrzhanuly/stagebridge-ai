"""Аддитивный catalog-diff двух PostgreSQL БД (structure_sync).

Строит план АДДИТИВНЫХ изменений (никаких DROP на цели) по системным каталогам.
Покрытие объектов:
  расширения, FDW / foreign servers / user mappings, типы (enum/composite/domain),
  sequences, aggregates, таблицы (в т.ч. партиционированные и foreign), колонки
  (в т.ч. generated/identity), индексы, constraints, RLS-политики, matviews,
  функции/процедуры, вьюхи, триггеры, event-триггеры, публикации, комментарии.

Объекты расширений (pg_depend.deptype='e') и системные схемы исключаются везде.
Все операции синхронные (psycopg2), вызываются из Celery-задачи.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.models.server import Server
from app.services.crypto import decrypt
from app.services.backup_service import _pg_bin, restore_pg_dump_local

LogCb = Callable[[str, dict], None] | None

_SYS_SCHEMAS = ("pg_catalog", "information_schema")
_NOT_EXTENSION = "oid NOT IN (SELECT objid FROM pg_depend WHERE deptype = 'e')"


def _connect(server: Server, database: str):
    password = decrypt(server.admin_password_encrypted)
    return psycopg2.connect(
        host=server.host, port=server.port, user=server.admin_user,
        password=password, dbname=database, connect_timeout=15,
    )


def _log(cb: LogCb, source: str, line: str) -> None:
    if cb:
        cb("log", {"source": source, "line": line})


def _fetch(conn, sql, params=None) -> list:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def _opts(arr) -> str:
    """text[] вида {'key=val',...} → OPTIONS (key 'val', ...)."""
    if not arr:
        return ""
    parts = []
    for item in arr:
        if "=" in item:
            k, v = item.split("=", 1)
            parts.append(f"{k} '{v}'")
    return f" OPTIONS ({', '.join(parts)})" if parts else ""


# ─────────────────────────── интроспекция ────────────────────────────

def _extensions(conn) -> set[str]:
    return {r[0] for r in _fetch(conn, "SELECT extname FROM pg_extension")}


def _fdws(conn) -> dict[str, str]:
    rows = _fetch(conn, f"""
        SELECT w.fdwname, h.proname, v.proname, w.fdwoptions
        FROM pg_foreign_data_wrapper w
        LEFT JOIN pg_proc h ON h.oid = w.fdwhandler
        LEFT JOIN pg_proc v ON v.oid = w.fdwvalidator
        WHERE w.{_NOT_EXTENSION}
    """)
    out = {}
    for name, handler, validator, options in rows:
        ddl = f'CREATE FOREIGN DATA WRAPPER "{name}"'
        if handler:
            ddl += f' HANDLER "{handler}"'
        if validator:
            ddl += f' VALIDATOR "{validator}"'
        ddl += _opts(options)
        out[name] = ddl
    return out


def _foreign_servers(conn) -> dict[str, str]:
    rows = _fetch(conn, f"""
        SELECT s.srvname, w.fdwname, s.srvtype, s.srvversion, s.srvoptions
        FROM pg_foreign_server s
        JOIN pg_foreign_data_wrapper w ON w.oid = s.srvfdw
        WHERE s.{_NOT_EXTENSION}
    """)
    out = {}
    for name, fdw, srvtype, srvversion, options in rows:
        ddl = f'CREATE SERVER "{name}"'
        if srvtype:
            ddl += f" TYPE '{srvtype}'"
        if srvversion:
            ddl += f" VERSION '{srvversion}'"
        ddl += f' FOREIGN DATA WRAPPER "{fdw}"' + _opts(options)
        out[name] = ddl
    return out


def _user_mappings(conn) -> dict[str, str]:
    rows = _fetch(conn, """
        SELECT srvname, usename, umoptions FROM pg_user_mappings
    """)
    out = {}
    for srv, usename, options in rows:
        who = "PUBLIC" if usename == "public" or usename is None else f'"{usename}"'
        ddl = f'CREATE USER MAPPING FOR {who} SERVER "{srv}"' + _opts(options)
        out[f"{srv}|{usename}"] = ddl
    return out


def _tableish(conn, relkinds: str) -> list[str]:
    """Список schema.name для указанных relkind, без партиций-детей и extension."""
    return [f"{r[0]}.{r[1]}" for r in _fetch(conn, f"""
        SELECT n.nspname, c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ({relkinds})
          AND NOT c.relispartition
          AND n.nspname NOT IN %s
          AND n.nspname NOT LIKE 'pg_temp%%' AND n.nspname NOT LIKE 'pg_toast%%'
          AND c.{_NOT_EXTENSION}
        ORDER BY 1, 2
    """, (_SYS_SCHEMAS,))]


def _partitions_of(conn, parents: list[str]) -> list[str]:
    """Все таблицы-партиции (рекурсивно) для указанных партиционированных родителей."""
    out: list[str] = []
    for q in parents:
        schema, name = q.split(".", 1)
        rows = _fetch(conn, """
            SELECT n.nspname, c.relname
            FROM pg_inherits i
            JOIN pg_class c ON c.oid = i.inhrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE i.inhparent = (quote_ident(%s) || '.' || quote_ident(%s))::regclass
        """, (schema, name))
        out += [f"{r[0]}.{r[1]}" for r in rows]
    return out


def _is_partitioned(conn, qualified: str) -> bool:
    schema, name = qualified.split(".", 1)
    rows = _fetch(conn, """
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'p' AND n.nspname = %s AND c.relname = %s
    """, (schema, name))
    return bool(rows)


def _table_columns(conn, schema: str, table: str) -> dict[str, dict]:
    rows = _fetch(conn, """
        SELECT a.attname, format_type(a.atttypid, a.atttypmod),
               pg_get_expr(d.adbin, d.adrelid), a.attnotnull,
               a.attgenerated, a.attidentity
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = %s AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
    """, (schema, table))
    return {r[0]: {"type": r[1], "default": r[2], "notnull": r[3],
                   "generated": r[4], "identity": r[5]} for r in rows}


def _column_ddl(schema: str, table: str, col: str, meta: dict) -> str:
    base = f'ALTER TABLE "{schema}"."{table}" ADD COLUMN IF NOT EXISTS "{col}" {meta["type"]}'
    if meta.get("generated") == "s" and meta.get("default"):
        return base + f' GENERATED ALWAYS AS ({meta["default"]}) STORED'
    if meta.get("identity") in ("a", "d"):
        kind = "ALWAYS" if meta["identity"] == "a" else "BY DEFAULT"
        return base + f" GENERATED {kind} AS IDENTITY"
    if meta.get("default"):
        base += f' DEFAULT {meta["default"]}'
    return base


def _sequences(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for sch, name, inc, mn, mx, start, cache, cycle in _fetch(conn, f"""
        SELECT s.schemaname, s.sequencename, s.increment_by, s.min_value, s.max_value,
               s.start_value, s.cache_size, s.cycle
        FROM pg_sequences s
        JOIN pg_class c ON c.relname = s.sequencename
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = s.schemaname
        WHERE c.relkind = 'S' AND s.schemaname NOT IN %s AND c.{_NOT_EXTENSION}
          AND NOT EXISTS (SELECT 1 FROM pg_depend dep WHERE dep.objid = c.oid AND dep.deptype IN ('a','i'))
    """, (_SYS_SCHEMAS,)):
        out[f"{sch}.{name}"] = (
            f'CREATE SEQUENCE IF NOT EXISTS "{sch}"."{name}" INCREMENT BY {inc}'
            f" MINVALUE {mn} MAXVALUE {mx} START WITH {start} CACHE {cache}"
            + (" CYCLE" if cycle else "")
        )
    return out


def _aggregates(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for sch, name, args, sfunc, stype, finalfn, initval in _fetch(conn, f"""
        SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid),
               a.aggtransfn::regproc::text, format_type(a.aggtranstype, NULL),
               NULLIF(a.aggfinalfn, 0)::regproc::text, a.agginitval
        FROM pg_aggregate a
        JOIN pg_proc p ON p.oid = a.aggfnoid
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN %s AND p.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        parts = [f"SFUNC = {sfunc}", f"STYPE = {stype}"]
        if finalfn:
            parts.append(f"FINALFUNC = {finalfn}")
        if initval is not None:
            parts.append(f"INITCOND = '{initval}'")
        out[f"{sch}.{name}({args})"] = (
            f'CREATE AGGREGATE "{sch}"."{name}" ({args}) (' + ", ".join(parts) + ")"
        )
    return out


def _indexes(conn) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for sch, tbl, idx, ddl in _fetch(conn, f"""
        SELECT n.nspname, t.relname, i.relname, pg_get_indexdef(ix.indexrelid)
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname NOT IN %s AND i.{_NOT_EXTENSION}
          AND ix.indexrelid NOT IN (SELECT conindid FROM pg_constraint WHERE conindid <> 0)
    """, (_SYS_SCHEMAS,)):
        out[f"{sch}.{idx}"] = (f"{sch}.{tbl}", ddl)
    return out


def _constraints(conn) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for sch, tbl, conname, condef in _fetch(conn, f"""
        SELECT n.nspname, t.relname, c.conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype IN ('c','f','u','p') AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        q = f"{sch}.{tbl}"
        out[f"{q}|{conname}"] = (q, f'ALTER TABLE "{sch}"."{tbl}" ADD CONSTRAINT "{conname}" {condef}')
    return out


def _rls(conn) -> tuple[dict[str, str], dict[str, str]]:
    """(enable_by_table, policies_by_key). enable — ALTER TABLE ENABLE RLS."""
    enable: dict[str, str] = {}
    for sch, tbl in _fetch(conn, f"""
        SELECT n.nspname, c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relrowsecurity AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        enable[f"{sch}.{tbl}"] = f'ALTER TABLE "{sch}"."{tbl}" ENABLE ROW LEVEL SECURITY'

    policies: dict[str, str] = {}
    for sch, tbl, pol, perm, roles, cmd, qual, chk in _fetch(conn, """
        SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
        FROM pg_policies WHERE schemaname NOT IN ('pg_catalog','information_schema')
    """):
        ddl = f'CREATE POLICY "{pol}" ON "{sch}"."{tbl}" AS {perm} FOR {cmd}'
        role_list = "PUBLIC" if not roles or list(roles) == ["public"] else ", ".join(f'"{r}"' for r in roles)
        ddl += f" TO {role_list}"
        if qual:
            ddl += f" USING ({qual})"
        if chk:
            ddl += f" WITH CHECK ({chk})"
        policies[f"{sch}.{tbl}.{pol}"] = ddl
    return enable, policies


def _function_defs(conn) -> list[str]:
    return [r[0] for r in _fetch(conn, f"""
        SELECT pg_get_functiondef(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN %s AND p.prokind IN ('f','p','w') AND p.{_NOT_EXTENSION}
        ORDER BY n.nspname, p.proname
    """, (_SYS_SCHEMAS,)) if r[0]]


def _view_defs(conn) -> list[str]:
    return [r[0] for r in _fetch(conn, f"""
        SELECT 'CREATE OR REPLACE VIEW ' || quote_ident(n.nspname) || '.'
               || quote_ident(c.relname) || ' AS ' || pg_get_viewdef(c.oid, true)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'v' AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
        ORDER BY 1
    """, (_SYS_SCHEMAS,)) if r[0]]


def _matviews(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for sch, name, vdef in _fetch(conn, f"""
        SELECT n.nspname, c.relname, pg_get_viewdef(c.oid, true)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'm' AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        out[f"{sch}.{name}"] = f'CREATE MATERIALIZED VIEW IF NOT EXISTS "{sch}"."{name}" AS {vdef} WITH NO DATA'
    return out


def _trigger_defs(conn) -> list[str]:
    out: list[str] = []
    for sch, tbl, tg, tgdef in _fetch(conn, f"""
        SELECT n.nspname, c.relname, t.tgname, pg_get_triggerdef(t.oid)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal AND n.nspname NOT IN %s AND t.{_NOT_EXTENSION}
        ORDER BY 1, 2, 3
    """, (_SYS_SCHEMAS,)):
        out.append(f'DROP TRIGGER IF EXISTS "{tg}" ON "{sch}"."{tbl}";\n{tgdef}')
    return out


def _event_triggers(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, event, fn, tags in _fetch(conn, f"""
        SELECT evtname, evtevent, evtfoid::regproc::text, evttags
        FROM pg_event_trigger WHERE {_NOT_EXTENSION.replace('oid', 'pg_event_trigger.oid')}
    """):
        ddl = f'DROP EVENT TRIGGER IF EXISTS "{name}";\nCREATE EVENT TRIGGER "{name}" ON {event}'
        if tags:
            ddl += " WHEN TAG IN (" + ", ".join(f"'{t}'" for t in tags) + ")"
        ddl += f" EXECUTE FUNCTION {fn}()"
        out[name] = ddl
    return out


def _publications(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, alltables, ins, upd, dele, trunc in _fetch(conn, """
        SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate
        FROM pg_publication
    """):
        acts = [a for a, on in (("insert", ins), ("update", upd), ("delete", dele), ("truncate", trunc)) if on]
        opts = f" WITH (publish = '{', '.join(acts)}')" if acts else ""
        if alltables:
            out[name] = f'CREATE PUBLICATION "{name}" FOR ALL TABLES{opts}'
        else:
            tbls = _fetch(conn, "SELECT schemaname, tablename FROM pg_publication_tables WHERE pubname = %s", (name,))
            if tbls:
                tlist = ", ".join(f'"{s}"."{t}"' for s, t in tbls)
                out[name] = f'CREATE PUBLICATION "{name}" FOR TABLE {tlist}{opts}'
            else:
                out[name] = f'CREATE PUBLICATION "{name}"{opts}'
    return out


def _comments(conn) -> list[str]:
    stmts: list[str] = []
    # таблицы/вьюхи/matview/foreign/sequence
    for kind, ident, descr in _fetch(conn, f"""
        SELECT CASE c.relkind WHEN 'r' THEN 'TABLE' WHEN 'p' THEN 'TABLE' WHEN 'v' THEN 'VIEW'
                              WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE'
                              WHEN 'S' THEN 'SEQUENCE' END,
               quote_ident(n.nspname) || '.' || quote_ident(c.relname), d.description
        FROM pg_description d
        JOIN pg_class c ON c.oid = d.objoid AND d.classoid = 'pg_class'::regclass AND d.objsubid = 0
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        stmts.append(f"COMMENT ON {kind} {ident} IS {_lit(descr)}")
    # колонки
    for ident, col, descr in _fetch(conn, f"""
        SELECT quote_ident(n.nspname) || '.' || quote_ident(c.relname), quote_ident(a.attname), d.description
        FROM pg_description d
        JOIN pg_class c ON c.oid = d.objoid AND d.classoid = 'pg_class'::regclass AND d.objsubid > 0
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        stmts.append(f"COMMENT ON COLUMN {ident}.{col} IS {_lit(descr)}")
    # функции
    for sig, descr in _fetch(conn, f"""
        SELECT p.oid::regprocedure::text, d.description
        FROM pg_description d
        JOIN pg_proc p ON p.oid = d.objoid AND d.classoid = 'pg_proc'::regclass
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN %s AND p.prokind IN ('f','p') AND p.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        stmts.append(f"COMMENT ON FUNCTION {sig} IS {_lit(descr)}")
    return stmts


def _lit(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


def _types(conn) -> dict[str, str]:
    result: dict[str, str] = {}
    for schema, name, labels in _fetch(conn, f"""
        SELECT n.nspname, t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE t.typtype = 'e' AND n.nspname NOT IN %s AND t.{_NOT_EXTENSION}
        GROUP BY 1, 2
    """, (_SYS_SCHEMAS,)):
        vals = ", ".join(_lit(str(l)) for l in labels)
        result[f"{schema}.{name}"] = f'CREATE TYPE "{schema}"."{name}" AS ENUM ({vals})'

    for schema, name, relid in _fetch(conn, f"""
        SELECT n.nspname, t.typname, t.typrelid
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typtype = 'c' AND n.nspname NOT IN %s
          AND t.typrelid IN (SELECT oid FROM pg_class WHERE relkind = 'c') AND t.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        cols = ", ".join(f'"{r[0]}" {r[1]}' for r in _fetch(conn, """
            SELECT a.attname, format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (relid,)))
        result[f"{schema}.{name}"] = f'CREATE TYPE "{schema}"."{name}" AS ({cols})'

    for schema, name, base, notnull, default in _fetch(conn, f"""
        SELECT n.nspname, t.typname, format_type(t.typbasetype, t.typtypmod),
               t.typnotnull, pg_get_expr(t.typdefaultbin, 0)
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typtype = 'd' AND n.nspname NOT IN %s AND t.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        ddl = f'CREATE DOMAIN "{schema}"."{name}" AS {base}'
        if default:
            ddl += f" DEFAULT {default}"
        if notnull:
            ddl += " NOT NULL"
        result[f"{schema}.{name}"] = ddl
    return result


def _schemas(conn) -> set[str]:
    """Пользовательские схемы (namespace), кроме системных и созданных расширениями."""
    return {r[0] for r in _fetch(conn, """
        SELECT n.nspname FROM pg_namespace n
        WHERE n.nspname NOT IN %s
          AND n.nspname NOT LIKE 'pg_temp%%' AND n.nspname NOT LIKE 'pg_toast%%'
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d WHERE d.objid = n.oid AND d.deptype = 'e'
          )
    """, (_SYS_SCHEMAS,))}


def _enum_values(conn) -> dict[str, list[str]]:
    """{schema.name: [labels в порядке enumsortorder]} для enum-типов."""
    result: dict[str, list[str]] = {}
    for schema, name, labels in _fetch(conn, f"""
        SELECT n.nspname, t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE t.typtype = 'e' AND n.nspname NOT IN %s AND t.{_NOT_EXTENSION}
        GROUP BY 1, 2
    """, (_SYS_SCHEMAS,)):
        result[f"{schema}.{name}"] = [str(l) for l in labels]
    return result


def _collations(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for schema, name, prov, coll, ctype, determ in _fetch(conn, f"""
        SELECT n.nspname, c.collname, c.collprovider, c.collcollate, c.collctype,
               c.collisdeterministic
        FROM pg_collation c JOIN pg_namespace n ON n.oid = c.collnamespace
        WHERE n.nspname NOT IN %s AND c.{_NOT_EXTENSION} AND c.collname <> 'default'
    """, (_SYS_SCHEMAS,)):
        provider = {"i": "icu", "c": "libc", "d": "libc"}.get(prov, "libc")
        parts: list[str] = []
        if coll:
            parts.append(f"LC_COLLATE = {_lit(coll)}")
        if ctype:
            parts.append(f"LC_CTYPE = {_lit(ctype)}")
        parts.append(f"PROVIDER = {provider}")
        if determ is False:
            parts.append("DETERMINISTIC = false")
        out[f"{schema}.{name}"] = f'CREATE COLLATION IF NOT EXISTS "{schema}"."{name}" ({", ".join(parts)})'
    return out


def _operators(conn) -> dict[str, str]:
    """CREATE OPERATOR (без commutator/negator — чтобы не ловить циклы; их допишет диф позже при повторном прогоне)."""
    out: dict[str, str] = {}
    for schema, name, lt, rt, code in _fetch(conn, f"""
        SELECT n.nspname, o.oprname,
               CASE WHEN o.oprleft = 0 THEN NULL ELSE format_type(o.oprleft, NULL) END,
               CASE WHEN o.oprright = 0 THEN NULL ELSE format_type(o.oprright, NULL) END,
               o.oprcode::regproc::text
        FROM pg_operator o JOIN pg_namespace n ON n.oid = o.oprnamespace
        WHERE n.nspname NOT IN %s AND o.{_NOT_EXTENSION} AND o.oprcode <> 0
    """, (_SYS_SCHEMAS,)):
        parts = [f"FUNCTION = {code}"]
        if lt:
            parts.append(f"LEFTARG = {lt}")
        if rt:
            parts.append(f"RIGHTARG = {rt}")
        out[f"{schema}.{name}({lt},{rt})"] = f'CREATE OPERATOR "{schema}".{name} ({", ".join(parts)})'
    return out


def _casts(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for src, tgt, func, ctx, method in _fetch(conn, f"""
        SELECT format_type(c.castsource, NULL), format_type(c.casttarget, NULL),
               CASE WHEN c.castfunc = 0 THEN NULL ELSE c.castfunc::regprocedure::text END,
               c.castcontext, c.castmethod
        FROM pg_cast c
        WHERE c.{_NOT_EXTENSION}
          AND c.castsource IN (
              SELECT t.oid FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
              WHERE n.nspname NOT IN %s
          )
    """, (_SYS_SCHEMAS,)):
        if method == "i":
            body = "WITH INOUT"
        elif method == "f" and func:
            body = f"WITH FUNCTION {func}"
        else:
            body = "WITHOUT FUNCTION"
        extra = " AS ASSIGNMENT" if ctx == "a" else (" AS IMPLICIT" if ctx == "i" else "")
        out[f"{src}=>{tgt}"] = f"CREATE CAST ({src} AS {tgt}) {body}{extra}"
    return out


def _rules(conn) -> dict[str, str]:
    """Rewrite-правила (pg_rewrite), кроме внутренних _RETURN у вьюх."""
    out: dict[str, str] = {}
    for schema, tbl, rule, oid in _fetch(conn, f"""
        SELECT n.nspname, c.relname, r.rulename, r.oid
        FROM pg_rewrite r
        JOIN pg_class c ON c.oid = r.ev_class
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE r.rulename <> '_RETURN' AND n.nspname NOT IN %s AND c.relkind IN ('r', 'v')
    """, (_SYS_SCHEMAS,)):
        got = _fetch(conn, "SELECT pg_get_ruledef(%s)", (oid,))
        if got and got[0][0]:
            out[f"{schema}.{tbl}.{rule}"] = got[0][0].rstrip(";")
    return out


def _ts_dicts(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for schema, name, tsch, tmpl, opts in _fetch(conn, f"""
        SELECT n.nspname, d.dictname, tn.nspname, t.tmplname, d.dictinitoption
        FROM pg_ts_dict d
        JOIN pg_namespace n ON n.oid = d.dictnamespace
        JOIN pg_ts_template t ON t.oid = d.dicttemplate
        JOIN pg_namespace tn ON tn.oid = t.tmplnamespace
        WHERE n.nspname NOT IN %s AND d.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        parts = [f'TEMPLATE = "{tsch}"."{tmpl}"']
        if opts:
            parts.append(opts)
        out[f"{schema}.{name}"] = f'CREATE TEXT SEARCH DICTIONARY "{schema}"."{name}" ({", ".join(parts)})'
    return out


def _ts_configs(conn) -> dict[str, str]:
    out: dict[str, str] = {}
    for schema, name, psch, prs, oid in _fetch(conn, f"""
        SELECT n.nspname, c.cfgname, pn.nspname, p.prsname, c.oid
        FROM pg_ts_config c
        JOIN pg_namespace n ON n.oid = c.cfgnamespace
        JOIN pg_ts_parser p ON p.oid = c.cfgparser
        JOIN pg_namespace pn ON pn.oid = p.prsnamespace
        WHERE n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        stmts = [f'CREATE TEXT SEARCH CONFIGURATION "{schema}"."{name}" (PARSER = "{psch}"."{prs}")']
        by_tok: dict[str, list[str]] = {}
        for tok, dsch, dname in _fetch(conn, """
            SELECT (SELECT alias FROM ts_token_type(
                        (SELECT cfgparser FROM pg_ts_config WHERE oid = %s)) WHERE tokid = m.maptokentype),
                   dn.nspname, d.dictname
            FROM pg_ts_config_map m
            JOIN pg_ts_dict d ON d.oid = m.mapdict
            JOIN pg_namespace dn ON dn.oid = d.dictnamespace
            WHERE m.mapcfg = %s ORDER BY m.maptokentype, m.mapseqno
        """, (oid, oid)):
            if tok:
                by_tok.setdefault(tok, []).append(f'"{dsch}"."{dname}"')
        for tok, dicts in by_tok.items():
            stmts.append(
                f'ALTER TEXT SEARCH CONFIGURATION "{schema}"."{name}" '
                f'ADD MAPPING FOR {tok} WITH {", ".join(dicts)}'
            )
        out[f"{schema}.{name}"] = ";\n".join(stmts)
    return out


def _grants(conn) -> set[str]:
    """GRANT-ы на таблицы/вьюхи/sequences/функции/схемы (object-level ACL)."""
    out: set[str] = set()
    for nsp, rel, kind, priv, gr, grantable in _fetch(conn, f"""
        SELECT n.nspname, c.relname, c.relkind, a.privilege_type,
               CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
               a.is_grantable
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE c.relacl IS NOT NULL AND n.nspname NOT IN %s AND c.{_NOT_EXTENSION}
          AND c.relkind IN ('r', 'v', 'm', 'S', 'p', 'f')
    """, (_SYS_SCHEMAS,)):
        objtype = "SEQUENCE" if kind == "S" else "TABLE"
        wgo = " WITH GRANT OPTION" if grantable else ""
        out.add(f'GRANT {priv} ON {objtype} "{nsp}"."{rel}" TO {gr}{wgo}')
    for sig, priv, gr, grantable in _fetch(conn, f"""
        SELECT p.oid::regprocedure::text, a.privilege_type,
               CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
               a.is_grantable
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL aclexplode(p.proacl) a
        WHERE p.proacl IS NOT NULL AND n.nspname NOT IN %s AND p.{_NOT_EXTENSION}
    """, (_SYS_SCHEMAS,)):
        wgo = " WITH GRANT OPTION" if grantable else ""
        out.add(f"GRANT {priv} ON FUNCTION {sig} TO {gr}{wgo}")
    for nsp, priv, gr, grantable in _fetch(conn, f"""
        SELECT n.nspname, a.privilege_type,
               CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
               a.is_grantable
        FROM pg_namespace n
        CROSS JOIN LATERAL aclexplode(n.nspacl) a
        WHERE n.nspacl IS NOT NULL AND n.nspname NOT IN %s
    """, (_SYS_SCHEMAS,)):
        wgo = " WITH GRANT OPTION" if grantable else ""
        out.add(f'GRANT {priv} ON SCHEMA "{nsp}" TO {gr}{wgo}')
    return out


# ─────────────────────────── построение плана ────────────────────────

@dataclass
class SyncPlan:
    schema_ddl: list[str] = field(default_factory=list)
    extension_ddl: list[str] = field(default_factory=list)
    fdw_ddl: list[str] = field(default_factory=list)
    server_ddl: list[str] = field(default_factory=list)
    usermapping_ddl: list[str] = field(default_factory=list)
    type_ddl: list[str] = field(default_factory=list)
    sequence_ddl: list[str] = field(default_factory=list)
    aggregate_ddl: list[str] = field(default_factory=list)
    new_tables: list[str] = field(default_factory=list)
    column_alters: list[str] = field(default_factory=list)
    index_ddl: list[str] = field(default_factory=list)
    constraint_ddl: list[str] = field(default_factory=list)
    rls_ddl: list[str] = field(default_factory=list)
    matview_ddl: list[str] = field(default_factory=list)
    function_ddl: list[str] = field(default_factory=list)
    view_ddl: list[str] = field(default_factory=list)
    trigger_ddl: list[str] = field(default_factory=list)
    event_trigger_ddl: list[str] = field(default_factory=list)
    publication_ddl: list[str] = field(default_factory=list)
    comment_ddl: list[str] = field(default_factory=list)
    collation_ddl: list[str] = field(default_factory=list)
    operator_ddl: list[str] = field(default_factory=list)
    cast_ddl: list[str] = field(default_factory=list)
    textsearch_ddl: list[str] = field(default_factory=list)
    rule_ddl: list[str] = field(default_factory=list)
    grant_ddl: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "schemas": len(self.schema_ddl),
            "extensions": len(self.extension_ddl), "fdw": len(self.fdw_ddl),
            "servers": len(self.server_ddl), "user_mappings": len(self.usermapping_ddl),
            "types": len(self.type_ddl), "sequences": len(self.sequence_ddl),
            "aggregates": len(self.aggregate_ddl), "new_tables": len(self.new_tables),
            "column_alters": len(self.column_alters), "indexes": len(self.index_ddl),
            "constraints": len(self.constraint_ddl), "rls": len(self.rls_ddl),
            "collations": len(self.collation_ddl), "operators": len(self.operator_ddl),
            "casts": len(self.cast_ddl), "textsearch": len(self.textsearch_ddl),
            "rules": len(self.rule_ddl), "grants": len(self.grant_ddl),
            "matviews": len(self.matview_ddl), "functions": len(self.function_ddl),
            "views": len(self.view_ddl), "triggers": len(self.trigger_ddl),
            "event_triggers": len(self.event_trigger_ddl), "publications": len(self.publication_ddl),
            "comments": len(self.comment_ddl), "notes": self.notes,
        }

    def as_sql(self) -> str:
        blocks: list[str] = []
        if self.new_tables:
            blocks.append("-- НОВЫЕ ТАБЛИЦЫ (через pg_dump):\n-- " + "\n-- ".join(self.new_tables))
        for title, items in (
            ("СХЕМЫ", self.schema_ddl),
            ("РАСШИРЕНИЯ", self.extension_ddl), ("FDW", self.fdw_ddl),
            ("FOREIGN SERVERS", self.server_ddl), ("USER MAPPINGS", self.usermapping_ddl),
            ("ТИПЫ", self.type_ddl), ("SEQUENCES", self.sequence_ddl),
            ("AGGREGATES", self.aggregate_ddl), ("КОЛОНКИ", self.column_alters),
            ("ИНДЕКСЫ", self.index_ddl), ("CONSTRAINTS", self.constraint_ddl),
            ("RLS", self.rls_ddl), ("MATVIEWS", self.matview_ddl),
            ("ФУНКЦИИ", self.function_ddl), ("VIEWS", self.view_ddl),
            ("ТРИГГЕРЫ", self.trigger_ddl), ("EVENT TRIGGERS", self.event_trigger_ddl),
            ("PUBLICATIONS", self.publication_ddl), ("COMMENTS", self.comment_ddl),
            ("COLLATIONS", self.collation_ddl), ("OPERATORS", self.operator_ddl),
            ("CASTS", self.cast_ddl), ("TEXT SEARCH", self.textsearch_ddl),
            ("RULES", self.rule_ddl), ("GRANTS", self.grant_ddl),
        ):
            if items:
                blocks.append(f"-- {title}:\n" + ";\n".join(items) + ";")
        return "\n\n".join(blocks)


def build_plan(test_server: Server, test_db: str, temp_server: Server, temp_db: str) -> SyncPlan:
    plan = SyncPlan()
    tc = _connect(test_server, test_db)
    try:
        pc = _connect(temp_server, temp_db)  # если упадёт — tc закроется в finally ниже
    except Exception:
        tc.close()
        raise
    try:
        # схемы (namespace) — создаём недостающие ДО всего остального,
        # иначе объекты в новой схеме упадут с ошибкой.
        plan.schema_ddl = [f'CREATE SCHEMA IF NOT EXISTS "{s}"'
                           for s in sorted(_schemas(tc) - _schemas(pc))]

        # расширения
        plan.extension_ddl = [f'CREATE EXTENSION IF NOT EXISTS "{e}"'
                              for e in sorted(_extensions(tc) - _extensions(pc))]

        # FDW / servers / user mappings
        t_fdw, p_fdw = _fdws(tc), _fdws(pc)
        plan.fdw_ddl = [d for k, d in t_fdw.items() if k not in p_fdw]
        t_srv, p_srv = _foreign_servers(tc), _foreign_servers(pc)
        plan.server_ddl = [d for k, d in t_srv.items() if k not in p_srv]
        t_um, p_um = _user_mappings(tc), _user_mappings(pc)
        plan.usermapping_ddl = [d for k, d in t_um.items() if k not in p_um]

        # типы
        t_types, p_types = _types(tc), set(_types(pc).keys())
        plan.type_ddl = [d for k, d in t_types.items() if k not in p_types]

        # enum: новые значения в СУЩЕСТВУЮЩИХ типах (ALTER TYPE ADD VALUE).
        # AUTOCOMMIT в apply_statements позволяет ADD VALUE (PG 12+ и в tx нельзя).
        t_enum, p_enum = _enum_values(tc), _enum_values(pc)
        for key, t_vals in t_enum.items():
            if key not in p_enum:
                continue  # новый enum создаётся целиком через type_ddl выше
            existing = set(p_enum[key])
            sch, nm = key.split(".", 1)
            for i, label in enumerate(t_vals):
                if label in existing:
                    continue
                # ближайший следующий уже существующий сосед → вставляем ПЕРЕД ним
                # (сохраняет порядок enum); иначе значение допишется в конец.
                before_ref = next((v for v in t_vals[i + 1:] if v in existing), None)
                stmt = f'ALTER TYPE "{sch}"."{nm}" ADD VALUE IF NOT EXISTS {_lit(label)}'
                if before_ref:
                    stmt += f' BEFORE {_lit(before_ref)}'
                plan.type_ddl.append(stmt)

        # sequences (идемпотентно)
        plan.sequence_ddl = list(_sequences(tc).values())

        # aggregates
        t_agg, p_agg = _aggregates(tc), set(_aggregates(pc).keys())
        plan.aggregate_ddl = [d for k, d in t_agg.items() if k not in p_agg]

        # таблицы (r/p/f, без партиций-детей)
        test_tables = _tableish(tc, "'r','p','f'")
        temp_tables = set(_tableish(pc, "'r','p','f'"))
        new = [t for t in test_tables if t not in temp_tables]
        # раскрыть партиционированных родителей — включить их партиции в дамп
        parents = [t for t in new if _is_partitioned(tc, t)]
        plan.new_tables = new + _partitions_of(tc, parents)

        common = [t for t in _tableish(tc, "'r','p'") if t in temp_tables]
        common_set = set(common)

        # колонки (в т.ч. generated/identity)
        for q in common:
            schema, table = q.split(".", 1)
            t_cols = _table_columns(tc, schema, table)
            p_cols = _table_columns(pc, schema, table)
            for col, meta in t_cols.items():
                if col in p_cols:
                    continue
                if meta["notnull"] and not meta["default"] and not meta["generated"] and not meta["identity"]:
                    plan.notes.append(f'{q}.{col}: NOT NULL без DEFAULT — добавлено как nullable')
                plan.column_alters.append(_column_ddl(schema, table, col, meta))

        # индексы / constraints — на существующих таблицах
        t_idx, p_idx = _indexes(tc), set(_indexes(pc).keys())
        plan.index_ddl = [d for k, (tb, d) in t_idx.items() if k not in p_idx and tb in common_set]
        t_con, p_con = _constraints(tc), set(_constraints(pc).keys())
        plan.constraint_ddl = [d for k, (tb, d) in t_con.items() if k not in p_con and tb in common_set]

        # RLS
        t_en, t_pol = _rls(tc)
        p_en, p_pol = _rls(pc)
        rls: list[str] = [d for k, d in t_en.items() if k not in p_en]
        rls += [d for k, d in t_pol.items() if k not in p_pol]
        plan.rls_ddl = rls

        # matviews
        t_mv, p_mv = _matviews(tc), set(_matviews(pc).keys())
        plan.matview_ddl = [d for k, d in t_mv.items() if k not in p_mv]

        # функции / вьюхи / триггеры — идемпотентно
        plan.function_ddl = _function_defs(tc)
        plan.view_ddl = _view_defs(tc)
        plan.trigger_ddl = _trigger_defs(tc)

        # event triggers / publications — идемпотентно / diff
        plan.event_trigger_ddl = list(_event_triggers(tc).values())
        t_pub, p_pub = _publications(tc), set(_publications(pc).keys())
        plan.publication_ddl = [d for k, d in t_pub.items() if k not in p_pub]

        # комментарии — идемпотентно
        plan.comment_ddl = _comments(tc)

        # collations / operators / casts / text search / rules — только новые по имени
        t_coll, p_coll = _collations(tc), set(_collations(pc).keys())
        plan.collation_ddl = [d for k, d in t_coll.items() if k not in p_coll]

        t_op, p_op = _operators(tc), set(_operators(pc).keys())
        plan.operator_ddl = [d for k, d in t_op.items() if k not in p_op]

        t_cast, p_cast = _casts(tc), set(_casts(pc).keys())
        plan.cast_ddl = [d for k, d in t_cast.items() if k not in p_cast]

        t_tsd, p_tsd = _ts_dicts(tc), set(_ts_dicts(pc).keys())
        p_tsc = set(_ts_configs(pc).keys())
        ts_cfg_stmts: list[str] = []
        for k, d in _ts_configs(tc).items():
            if k not in p_tsc:
                ts_cfg_stmts.extend(d.split(";\n"))
        plan.textsearch_ddl = [d for k, d in t_tsd.items() if k not in p_tsd] + ts_cfg_stmts

        t_rule, p_rule = _rules(tc), set(_rules(pc).keys())
        plan.rule_ddl = [d for k, d in t_rule.items() if k not in p_rule]

        # привилегии (object-level GRANT) — разница множеств
        plan.grant_ddl = sorted(_grants(tc) - _grants(pc))
    finally:
        tc.close()
        pc.close()
    return plan


# ─────────────────────────── применение ──────────────────────────────

def apply_statements(server: Server, database: str, statements: list[str],
                     on_progress: LogCb = None, label: str = "apply") -> tuple[int, list[str]]:
    if not statements:
        return 0, []
    conn = _connect(server, database)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    ok, errors = 0, []
    try:
        for stmt in statements:
            try:
                with conn.cursor() as cur:
                    cur.execute(stmt)
                ok += 1
            except Exception as e:  # noqa: BLE001
                msg = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
                errors.append(f"[{label}] {msg}")
                _log(on_progress, "error", f"{label}: {msg}")
    finally:
        conn.close()
    if on_progress:
        _log(on_progress, "info", f"{label}: применено {ok}/{len(statements)}, ошибок {len(errors)}")
    return ok, errors


def copy_tables(src_server: Server, src_db: str, dst_server: Server, dst_db: str,
                tables: list[str], include_data: bool, on_progress: LogCb = None) -> None:
    if not tables:
        return
    password = decrypt(src_server.admin_password_encrypted)
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp_path = os.path.join(tempfile.gettempdir(), f"newtables_{src_db}_{ts}.sql")
    table_args: list[str] = []
    for t in tables:
        table_args += ["-t", t]
    cmd = [
        _pg_bin(src_server, src_db, "pg_dump"),
        "-h", src_server.host, "-p", str(src_server.port), "-U", src_server.admin_user,
        "-Fp", "--no-owner", "--no-privileges",
        *([] if include_data else ["--schema-only"]),
        *table_args, "-f", tmp_path, src_db,
    ]
    _log(on_progress, "info", f"pg_dump новых таблиц ({len(tables)})")
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError("pg_dump новых таблиц упал: " + "\n".join(proc.stderr.strip().splitlines()[-10:]))
        restore_pg_dump_local(dst_server, dst_db, tmp_path, backup_format="plain",
                              on_progress=on_progress, clean=False)
    finally:
        # чистим temp при ЛЮБОМ исходе (таймаут / ненулевой код / ошибка restore)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def count_rows(server: Server, database: str, qualified_table: str) -> int | None:
    schema, table = qualified_table.split(".", 1)
    try:
        conn = _connect(server, database)
        try:
            with conn.cursor() as cur:
                cur.execute(f'SELECT count(*) FROM "{schema}"."{table}"')
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None
