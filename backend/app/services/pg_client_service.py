import json
import re
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager
from collections.abc import Callable
from pathlib import Path

import redis as sync_redis

from app.config import settings

_PKG_RE = re.compile(r"^postgresql-client-(\d+)$")
_PG_BIN_ROOT = Path("/usr/lib/postgresql")
_install_lock = threading.Lock()
_available_lock = threading.Lock()
_available_packages: list[dict] | None = None
_available_loaded_at: float = 0.0
_AVAILABLE_TTL = 3600.0
_REDIS_PACKAGES_KEY = "pgadmin:pg_client:available_packages"
_REDIS_PACKAGES_TS_KEY = "pgadmin:pg_client:available_packages_ts"
_PG_CLIENT_OPS_LOCK_KEY = "pgadmin:lock:pg_client_ops"
_PG_CLIENT_OPS_LOCK_TTL = 900
_PG_CLIENT_OPS_WAIT_SEC = 600

LogCallback = Callable[[str, str], None] | None
StageCallback = Callable[[str, str | None], None] | None


def _client_root(major: int) -> Path:
    return _PG_BIN_ROOT / str(major)


def _pg_dump_path(major: int) -> Path:
    return _client_root(major) / "bin" / "pg_dump"


def is_installed(major: int) -> bool:
    return _pg_dump_path(major).is_file()


def list_installed_majors() -> list[int]:
    if not _PG_BIN_ROOT.is_dir():
        return []
    majors: list[int] = []
    for entry in _PG_BIN_ROOT.iterdir():
        if entry.is_dir() and entry.name.isdigit() and _pg_dump_path(int(entry.name)).is_file():
            majors.append(int(entry.name))
    return sorted(majors)


def _emit_log(on_log: LogCallback, source: str, line: str) -> None:
    if on_log and line.strip():
        on_log(source, line.rstrip())


def _emit_stage(on_stage: StageCallback, stage: str, message: str | None = None) -> None:
    if on_stage:
        on_stage(stage, message)


def _run_apt_command(
    cmd: list[str],
    *,
    on_log: LogCallback = None,
    timeout: int = 600,
) -> tuple[int, str]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return 127, "apt-get недоступен в контейнере"

    output_lines: list[str] = []
    if proc.stdout:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                output_lines.append(line)
                _emit_log(on_log, "apt", line)

    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return 124, "Превышено время ожидания apt-get"

    tail = "\n".join(output_lines[-20:]).strip()
    return returncode, tail


def _is_apt_package_installed(major: int) -> bool:
    pkg = f"postgresql-client-{major}"
    try:
        proc = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    if proc.returncode != 0:
        return False
    return proc.stdout.strip().startswith("install ok")


def _remove_client_files(
    major: int,
    *,
    on_log: LogCallback = None,
) -> tuple[bool, str]:
    root = _client_root(major)
    if not root.exists():
        return True, ""
    _emit_log(on_log, "fs", f"$ rm -rf {root}")
    try:
        shutil.rmtree(root)
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _apt_candidate_version(package: str) -> str | None:
    try:
        proc = subprocess.run(
            ["apt-cache", "policy", package],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("Candidate:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate and candidate != "(none)":
                return candidate
    return None


def _run_apt_update(on_log: LogCallback = None, on_stage: StageCallback = None) -> tuple[bool, str]:
    _emit_stage(on_stage, "update", "apt-get update…")
    _emit_log(on_log, "apt", "$ apt-get update -qq")
    code, tail = _run_apt_command(["apt-get", "update", "-qq"], on_log=on_log, timeout=180)
    if code != 0:
        return False, tail or "apt-get update failed"
    return True, ""


def _fetch_available_packages(*, on_log: LogCallback = None) -> list[dict]:
    _emit_log(on_log, "apt", "$ apt-cache pkgnames")
    try:
        proc = subprocess.run(
            ["apt-cache", "pkgnames"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        _emit_log(on_log, "apt", str(exc))
        return []

    if proc.returncode != 0:
        tail = (proc.stdout or proc.stderr or "").strip()[-300:]
        _emit_log(on_log, "apt", tail or "apt-cache pkgnames failed")
        return []

    majors: set[int] = set()
    for line in proc.stdout.splitlines():
        match = _PKG_RE.match(line.strip())
        if match:
            majors.add(int(match.group(1)))

    _emit_log(on_log, "apt", f"Найдено {len(majors)} пакетов postgresql-client-*")

    packages: list[dict] = []
    for major in sorted(majors):
        package = f"postgresql-client-{major}"
        candidate = _apt_candidate_version(package)
        packages.append({
            "major": major,
            "package": package,
            "candidate": candidate,
            "installed": is_installed(major),
        })
    if packages:
        majors_line = ", ".join(str(item["major"]) for item in packages)
        _emit_log(on_log, "apt", f"Версии: {majors_line}")
    return packages


def _redis_client() -> sync_redis.Redis:
    return sync_redis.from_url(settings.redis_url)


@contextmanager
def _pg_client_ops_lock(on_stage: StageCallback = None):
    """Межпроцессная блокировка apt/PGDG (Celery worker -c>1)."""
    r = _redis_client()
    acquired = False
    deadline = time.monotonic() + _PG_CLIENT_OPS_WAIT_SEC
    waiting_logged = False
    try:
        while time.monotonic() < deadline:
            if r.set(_PG_CLIENT_OPS_LOCK_KEY, "1", nx=True, ex=_PG_CLIENT_OPS_LOCK_TTL):
                acquired = True
                break
            if on_stage and not waiting_logged:
                _emit_stage(on_stage, "preparing", "Ожидание завершения другой операции PG…")
                waiting_logged = True
            time.sleep(1.5)
        if not acquired:
            raise ValueError(
                "Другая операция PG-клиента (установка, удаление или загрузка PGDG) уже выполняется. "
                "Дождитесь завершения и повторите."
            )
        yield
    finally:
        if acquired:
            r.delete(_PG_CLIENT_OPS_LOCK_KEY)
        r.close()


def _load_packages_from_redis() -> tuple[list[dict] | None, float]:
    try:
        r = _redis_client()
        raw = r.get(_REDIS_PACKAGES_KEY)
        ts_raw = r.get(_REDIS_PACKAGES_TS_KEY)
        r.close()
        if not raw:
            return None, 0.0
        packages = json.loads(raw)
        ts = float(ts_raw) if ts_raw else 0.0
        return packages, ts
    except Exception:
        return None, 0.0


def _save_packages_to_redis(packages: list[dict]) -> None:
    if not packages:
        return
    try:
        r = _redis_client()
        r.set(_REDIS_PACKAGES_KEY, json.dumps(packages), ex=int(_AVAILABLE_TTL * 2))
        r.set(_REDIS_PACKAGES_TS_KEY, str(time.time()))
        r.close()
    except Exception:
        pass


def _refresh_installed_flags(packages: list[dict]) -> list[dict]:
    return [{**item, "installed": is_installed(item["major"])} for item in packages]


def _hydrate_available_cache() -> bool:
    """Подтягивает список пакетов из Redis в локальный кэш процесса."""
    global _available_packages, _available_loaded_at

    packages, ts = _load_packages_from_redis()
    if not packages:
        return False
    if (time.time() - ts) > _AVAILABLE_TTL:
        return False
    _available_packages = _refresh_installed_flags(packages)
    _available_loaded_at = time.monotonic()
    return True


def list_available_clients(
    *,
    refresh: bool = False,
    on_log: LogCallback = None,
    on_stage: StageCallback = None,
) -> dict:
    global _available_packages, _available_loaded_at

    with _available_lock:
        now = time.monotonic()
        local_stale = (
            _available_packages is None
            or len(_available_packages) == 0
            or (now - _available_loaded_at) > _AVAILABLE_TTL
        )
        repo_updated = False
        update_error = ""

        if local_stale:
            _hydrate_available_cache()

        if refresh:
            with _pg_client_ops_lock(on_stage):
                _emit_stage(on_stage, "preparing", "Загрузка списка из PGDG…")
                ok, update_error = _run_apt_update(on_log=on_log, on_stage=on_stage)
                repo_updated = ok
                if not ok:
                    return {
                        "ok": False,
                        "message": update_error,
                        "repo_updated": False,
                        "packages": _available_packages or [],
                    }
                _emit_stage(on_stage, "scan", "Чтение apt-cache pkgnames…")
                fetched = _fetch_available_packages(on_log=on_log)
                _available_packages = fetched
                _available_loaded_at = time.monotonic()
                if _available_packages:
                    _save_packages_to_redis(_available_packages)
                _emit_stage(
                    on_stage,
                    "completed",
                    f"Загружено {len(_available_packages)} пакетов postgresql-client-*",
                )

        return {
            "ok": True,
            "message": update_error,
            "repo_updated": repo_updated,
            "packages": _refresh_installed_flags(_available_packages or []),
        }


def invalidate_available_cache() -> None:
    global _available_packages, _available_loaded_at
    with _available_lock:
        _available_packages = None
        _available_loaded_at = 0.0
    try:
        r = _redis_client()
        r.delete(_REDIS_PACKAGES_KEY, _REDIS_PACKAGES_TS_KEY)
        r.close()
    except Exception:
        pass


def available_majors(*, refresh: bool = False) -> set[int]:
    result = list_available_clients(refresh=refresh)
    return {item["major"] for item in result.get("packages", [])}


def is_available_in_repo(major: int) -> bool:
    return major in available_majors(refresh=False)


def validate_manual_major(major: int) -> None:
    if major < 1:
        raise ValueError("Некорректная major-версия PostgreSQL")
    if major not in available_majors(refresh=False):
        raise ValueError(
            f"postgresql-client-{major} не найден в репозитории PGDG. "
            "Нажмите «Загрузить из PGDG» и выберите версию из списка."
        )


def validate_installable_major(major: int) -> None:
    if major < 1:
        raise ValueError("Некорректная major-версия PostgreSQL")
    if is_installed(major):
        return
    if major in available_majors(refresh=False):
        return
    pkg = f"postgresql-client-{major}"
    if _apt_candidate_version(pkg):
        return
    raise ValueError(
        f"Пакет {pkg} недоступен в apt/PGDG. "
        "Нажмите «Загрузить из PGDG» или проверьте сеть."
    )


def install_client(
    major: int,
    *,
    on_log: LogCallback = None,
    on_stage: StageCallback = None,
) -> dict:
    with _pg_client_ops_lock(on_stage):
        validate_installable_major(major)
        if is_installed(major):
            _emit_stage(on_stage, "completed", f"PostgreSQL client {major} уже установлен")
            return {"ok": True, "message": f"PostgreSQL client {major} уже установлен", "major": major}

        pkg = f"postgresql-client-{major}"
        with _install_lock:
            if is_installed(major):
                _emit_stage(on_stage, "completed", f"PostgreSQL client {major} уже установлен")
                return {"ok": True, "message": f"PostgreSQL client {major} уже установлен", "major": major}

            _emit_stage(on_stage, "preparing", f"Установка {pkg}")
            ok, err = _run_apt_update(on_log, on_stage)
            if not ok:
                return {"ok": False, "message": err}

            _emit_stage(on_stage, "install", f"apt-get install {pkg}")
            _emit_log(on_log, "apt", f"$ apt-get install -y --no-install-recommends {pkg}")
            code, tail = _run_apt_command(
                [
                    "apt-get", "install", "-y", "--no-install-recommends",
                    "-o", "Dpkg::Options::=--force-confdef",
                    "-o", "Dpkg::Options::=--force-confold",
                    pkg,
                ],
                on_log=on_log,
                timeout=600,
            )
            if code != 0:
                return {"ok": False, "message": tail[-500:] if tail else f"Не удалось установить {pkg}"}

        invalidate_available_cache()
        _emit_stage(on_stage, "verify", f"Проверка {_pg_dump_path(major)}")
        if not is_installed(major):
            return {"ok": False, "message": f"Пакет установлен, но {_pg_dump_path(major)} не найден"}

        _emit_stage(on_stage, "completed", f"PostgreSQL client {major} установлен")
        return {"ok": True, "message": f"PostgreSQL client {major} установлен", "major": major}


def uninstall_client(
    major: int,
    *,
    on_log: LogCallback = None,
    on_stage: StageCallback = None,
) -> dict:
    if major < 1:
        raise ValueError("Некорректная major-версия PostgreSQL")
    if not is_installed(major):
        _emit_stage(on_stage, "completed", f"PostgreSQL client {major} не установлен")
        return {"ok": True, "message": f"PostgreSQL client {major} не установлен", "major": major}

    pkg = f"postgresql-client-{major}"
    with _pg_client_ops_lock(on_stage):
        with _install_lock:
            apt_installed = _is_apt_package_installed(major)
            if apt_installed:
                _emit_stage(on_stage, "remove", f"apt-get remove {pkg}")
                _emit_log(on_log, "apt", f"$ apt-get remove -y --purge {pkg}")
                code, tail = _run_apt_command(
                    ["apt-get", "remove", "-y", "--purge", pkg],
                    on_log=on_log,
                    timeout=180,
                )
                if code != 0 and is_installed(major):
                    _emit_log(
                        on_log,
                        "apt",
                        "apt-get remove не удался — удаляем файлы клиента вручную",
                    )
                elif code != 0:
                    return {"ok": False, "message": tail[-500:] if tail else f"Не удалось удалить {pkg}"}
            else:
                _emit_stage(
                    on_stage,
                    "remove",
                    f"Пакет {pkg} не в dpkg — удаление файлов из {_client_root(major)}",
                )

            if is_installed(major):
                ok, err = _remove_client_files(major, on_log=on_log)
                if not ok:
                    return {"ok": False, "message": err or f"Не удалось удалить {_client_root(major)}"}

        invalidate_available_cache()
        _emit_stage(on_stage, "verify", "Проверка удаления")
        if is_installed(major):
            return {"ok": False, "message": f"Клиент {major} всё ещё присутствует после удаления"}

        _emit_stage(on_stage, "completed", f"PostgreSQL client {major} удалён")
        return {"ok": True, "message": f"PostgreSQL client {major} удалён", "major": major}


def bin_path(major: int) -> str | None:
    path = _pg_dump_path(major)
    return str(path) if path.is_file() else None
