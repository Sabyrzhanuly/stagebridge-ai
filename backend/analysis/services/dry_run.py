from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from analysis.models import AnalysisRun, ApprovedAction, DryRunLog

from .actions import required_action_types_for_success
from .connections import connect_to_target
from .localization import translate

NUMERIC_TEXT_RE = r"^\s*[+-]?((\d+(\.\d+)?)|(\.\d+))\s*$"


@dataclass
class DryRunResult:
    passed: bool
    transferred_rows: int = 0
    rejected_rows: int = 0
    validation_failures: int = 0
    logs: list[dict[str, Any]] = field(default_factory=list)


class DryRunExecutor:
    def __init__(self, analysis: AnalysisRun):
        self.analysis = analysis
        self.locale = analysis.locale
        self.sequence = 0
        self.logs: list[dict[str, Any]] = []

    def run(self) -> DryRunResult:
        if self.analysis.mode != AnalysisRun.Mode.DEMO:
            self._log("safety_gate", "failed", translate("dryrun.live_blocked", self.locale))
            return self._finish(DryRunResult(passed=False, validation_failures=1))
        self.analysis.dry_run_status = AnalysisRun.DryRunStatus.RUNNING
        self.analysis.save(update_fields=["dry_run_status", "updated_at"])
        DryRunLog.objects.filter(analysis=self.analysis).delete()
        approved_actions = list(self.analysis.actions.filter(approved=True))
        missing = required_action_types_for_success() - {action.action_type for action in approved_actions}
        if missing:
            result = DryRunResult(passed=False, validation_failures=len(missing))
            self._log("approval_gate", "failed", translate("dryrun.missing_actions", self.locale, actions=", ".join(sorted(missing))))
            return self._finish(result)

        try:
            with connect_to_target("prod", read_only=True) as prod_conn, connect_to_target("dryrun", read_only=False) as dry_conn:
                self._reset_dryrun(dry_conn)
                self._apply_development_schema(dry_conn)
                raw_counts = self._copy_production_rows(prod_conn, dry_conn)
                self._log("copy_source_data", "passed", translate("dryrun.copy_source", self.locale), sum(raw_counts.values()))
                transferred, rejected = self._apply_transformations(dry_conn, approved_actions)
                failures = self._validate(dry_conn)
                result = DryRunResult(
                    passed=failures == 0,
                    transferred_rows=transferred,
                    rejected_rows=rejected,
                    validation_failures=failures,
                    logs=self.logs,
                )
                return self._finish(result)
        except Exception as exc:
            self._log("dry_run_error", "failed", f"{translate('dryrun.failed', self.locale)}: {exc}")
            return self._finish(DryRunResult(passed=False, validation_failures=1, logs=self.logs))

    def _finish(self, result: DryRunResult) -> DryRunResult:
        result.logs = self.logs
        status = AnalysisRun.DryRunStatus.PASSED if result.passed else AnalysisRun.DryRunStatus.FAILED
        report = {
            **(self.analysis.report or {}),
            "status": translate("dryrun.passed" if result.passed else "dryrun.failed", self.locale),
            "transferredRows": result.transferred_rows,
            "rejectedRows": result.rejected_rows,
            "validationFailures": result.validation_failures,
            "limitation": translate("dryrun.limitation", self.locale),
            "logs": result.logs,
        }
        with transaction.atomic():
            self.analysis.dry_run_status = status
            self.analysis.report = report
            metrics = dict(self.analysis.metrics or {})
            metrics.update(
                {
                    "dryRunStatus": status,
                    "transferredRows": result.transferred_rows,
                    "validationFailures": result.validation_failures,
                    "approvedActions": self.analysis.actions.filter(approved=True).count(),
                }
            )
            self.analysis.metrics = metrics
            self.analysis.save(update_fields=["dry_run_status", "report", "metrics", "updated_at"])
            DryRunLog.objects.filter(analysis=self.analysis).delete()
            for entry in self.logs:
                DryRunLog.objects.create(analysis=self.analysis, **entry)
        return result

    def _log(self, step: str, status: str, message: str, rows_affected: int = 0, sql_preview: str = "") -> None:
        self.sequence += 1
        self.logs.append(
            {
                "sequence": self.sequence,
                "step": step,
                "status": status,
                "message": message,
                "rows_affected": int(rows_affected or 0),
                "sql_preview": sql_preview,
            }
        )

    def _reset_dryrun(self, conn) -> None:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute("SET search_path TO public")
        self._log("reset_dryrun_database", "passed", translate("dryrun.reset", self.locale))

    def _apply_development_schema(self, conn) -> None:
        statements = [
            "CREATE TYPE public.order_status AS ENUM ('pending', 'paid', 'shipped', 'refunded')",
            """
            CREATE TABLE public.users (
              id integer PRIMARY KEY,
              email varchar(255) UNIQUE,
              phone varchar(40) NOT NULL
            )
            """,
            """
            CREATE TABLE public.customer (
              id integer PRIMARY KEY,
              display_name varchar(255) NOT NULL
            )
            """,
            """
            CREATE TABLE public.orders (
              id integer PRIMARY KEY,
              customer_id integer REFERENCES public.customer(id),
              price numeric(10, 2),
              status public.order_status NOT NULL
            )
            """,
            "CREATE TABLE public.raw_users (id integer, email text, phone text)",
            "CREATE TABLE public.raw_customer (id integer, full_name text)",
            "CREATE TABLE public.raw_orders (id integer, customer_id integer, price text, status text)",
            "CREATE TABLE public.rejected_users (id integer, reason text, email text)",
            "CREATE TABLE public.rejected_orders (id integer, reason text, raw_price text, customer_id integer, status text)",
        ]
        for statement in statements:
            conn.execute(statement)
        self._log("apply_development_schema", "passed", translate("dryrun.apply_schema", self.locale), sql_preview="CREATE TYPE order_status; CREATE TABLE users/customer/orders;")

    def _copy_production_rows(self, prod_conn, dry_conn) -> dict[str, int]:
        counts: dict[str, int] = {}
        table_specs = {
            "users": ("SELECT id, email, phone FROM public.users ORDER BY id", "INSERT INTO public.raw_users (id, email, phone) VALUES (%(id)s, %(email)s, %(phone)s)"),
            "customer": ("SELECT id, full_name FROM public.customer ORDER BY id", "INSERT INTO public.raw_customer (id, full_name) VALUES (%(id)s, %(full_name)s)"),
            "orders": ("SELECT id, customer_id, price, status::text AS status FROM public.orders ORDER BY id", "INSERT INTO public.raw_orders (id, customer_id, price, status) VALUES (%(id)s, %(customer_id)s, %(price)s, %(status)s)"),
        }
        for name, (select_sql, insert_sql) in table_specs.items():
            rows = prod_conn.execute(select_sql).fetchall()
            if rows:
                with dry_conn.cursor() as cursor:
                    cursor.executemany(insert_sql, rows)
            counts[name] = len(rows)
        return counts

    def _apply_transformations(self, conn, actions: list[ApprovedAction]) -> tuple[int, int]:
        action_params = {action.action_type: action.parameters for action in actions}
        default_phone = action_params.get("backfill_null_with_default", {}).get("default_value", "000-000-0000")

        conn.execute(
            """
            INSERT INTO public.rejected_users (id, reason, email)
            SELECT id, 'duplicate_email', email
            FROM (
              SELECT id, email, row_number() OVER (PARTITION BY email ORDER BY id) AS rn
              FROM public.raw_users
            ) ranked
            WHERE rn > 1
            """
        )
        rejected_users = conn.execute("SELECT count(*) AS count FROM public.rejected_users").fetchone()["count"]
        conn.execute(
            """
            INSERT INTO public.users (id, email, phone)
            SELECT id, email, COALESCE(phone, %s)
            FROM (
              SELECT id, email, phone, row_number() OVER (PARTITION BY email ORDER BY id) AS rn
              FROM public.raw_users
            ) ranked
            WHERE rn = 1
            """,
            (default_phone,),
        )
        self._log("load_users", "passed", translate("dryrun.load_users", self.locale), rejected_users)

        conn.execute(
            """
            INSERT INTO public.customer (id, display_name)
            SELECT id, COALESCE(NULLIF(full_name, ''), 'Unnamed customer')
            FROM public.raw_customer
            """
        )
        self._log("map_customer_rename", "passed", translate("dryrun.map_customer", self.locale))

        mapping = action_params.get("map_enum_values", {}).get("mapping", {"cancelled": "refunded"})
        cancelled_target = mapping.get("cancelled", "refunded")
        if cancelled_target not in {"pending", "paid", "shipped", "refunded"}:
            raise ValueError(translate("dryrun.invalid_enum", self.locale))
        conn.execute(
            """
            INSERT INTO public.rejected_orders (id, reason, raw_price, customer_id, status)
            SELECT id,
                   CASE
                     WHEN NOT (price ~ %s) THEN 'invalid_numeric_price'
                     WHEN NOT EXISTS (SELECT 1 FROM public.customer c WHERE c.id = raw_orders.customer_id) THEN 'orphan_customer_id'
                     ELSE 'unsupported_status'
                   END,
                   price,
                   customer_id,
                   status
            FROM public.raw_orders
            WHERE NOT (price ~ %s)
               OR NOT EXISTS (SELECT 1 FROM public.customer c WHERE c.id = raw_orders.customer_id)
               OR (CASE WHEN status = 'cancelled' THEN %s ELSE status END) NOT IN ('pending', 'paid', 'shipped', 'refunded')
            """,
            (NUMERIC_TEXT_RE, NUMERIC_TEXT_RE, cancelled_target),
        )
        conn.execute(
            """
            INSERT INTO public.orders (id, customer_id, price, status)
            SELECT id,
                   customer_id,
                   price::numeric(10, 2),
                   (CASE WHEN status = 'cancelled' THEN %s ELSE status END)::public.order_status
            FROM public.raw_orders
            WHERE price ~ %s
              AND EXISTS (SELECT 1 FROM public.customer c WHERE c.id = raw_orders.customer_id)
              AND (CASE WHEN status = 'cancelled' THEN %s ELSE status END) IN ('pending', 'paid', 'shipped', 'refunded')
            """,
            (cancelled_target, NUMERIC_TEXT_RE, cancelled_target),
        )
        rejected_orders = conn.execute("SELECT count(*) AS count FROM public.rejected_orders").fetchone()["count"]
        self._log("load_orders", "passed", translate("dryrun.load_orders", self.locale), rejected_orders)

        transferred = sum(
            conn.execute(f"SELECT count(*) AS count FROM public.{table_name}").fetchone()["count"]
            for table_name in ("users", "customer", "orders")
        )
        rejected = rejected_users + rejected_orders
        return int(transferred), int(rejected)

    def _validate(self, conn) -> int:
        checks = [
            ("users_phone_not_null", "SELECT count(*) AS count FROM public.users WHERE phone IS NULL"),
            ("users_email_unique", "SELECT count(*) AS count FROM (SELECT email FROM public.users GROUP BY email HAVING count(*) > 1) d"),
            (
                "orders_customer_fk",
                "SELECT count(*) AS count FROM public.orders o WHERE NOT EXISTS (SELECT 1 FROM public.customer c WHERE c.id = o.customer_id)",
            ),
            (
                "orders_status_enum",
                "SELECT count(*) AS count FROM public.orders WHERE status::text NOT IN ('pending', 'paid', 'shipped', 'refunded')",
            ),
        ]
        failures = 0
        for name, query in checks:
            count = int(conn.execute(query).fetchone()["count"])
            status = "passed" if count == 0 else "failed"
            failures += 1 if count else 0
            self._log(name, status, translate("dryrun.validation_failures", self.locale, count=count), count)
        return failures
