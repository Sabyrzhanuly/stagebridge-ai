import subprocess
import tempfile
import os
import time
import threading
import hashlib
from datetime import datetime
from typing import Callable

from app.models.server import Server
from app.services.crypto import decrypt
from app.services import minio_service


def _detect_pg_major_version(server: Server, database: str) -> int:
    """Определяет major-версию PostgreSQL сервера через прямое подключение (fallback)."""
    try:
        import psycopg2
        password = decrypt(server.admin_password_encrypted)
        conn = psycopg2.connect(
            host=server.host, port=server.port,
            user=server.admin_user, password=password,
            dbname=database, connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("select current_setting('server_version_num')::int / 10000")
                row = cur.fetchone()
                return row[0] if row else 14
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 — не молчим: fallback на 14 виден в логе
        print(f"[backup] не удалось определить версию PG ({server.host}:{server.port}), "
              f"использую fallback 14: {type(e).__name__}: {e}", flush=True)
        return 14


def _pg_bin(server: Server, database: str, tool: str) -> str:
    """Возвращает путь к pg_dump/pg_restore нужной версии.

    Сначала берём pg_major_version из записи сервера (без лишнего подключения).
    Если не сохранено — определяем через прямое подключение.
    Если бинарник не установлен — выбрасываем понятную ошибку.
    """
    major = getattr(server, 'pg_major_version', None) or _detect_pg_major_version(server, database)
    path = f"/usr/lib/postgresql/{major}/bin/{tool}"
    if os.path.exists(path):
        return path
    raise RuntimeError(
        f"PostgreSQL client v{major} не установлен. "
        f"Установите его в «Настройки → PG Клиенты» (администратор платформы)."
    )


def get_db_size(server: Server, database: str) -> int | None:
    """Возвращает pg_database_size в байтах через синхронный psycopg2."""
    try:
        import psycopg2
        password = decrypt(server.admin_password_encrypted)
        conn = psycopg2.connect(
            host=server.host, port=server.port,
            user=server.admin_user, password=password,
            dbname=database, connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("select pg_database_size(%s)", (database,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _calculate_checksum(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _watch_file_growth(path: str, on_progress: Callable[[int], None], stop: threading.Event, interval: float = 1.0):
    while not stop.is_set():
        try:
            if os.path.exists(path):
                on_progress(os.path.getsize(path))
        except OSError:
            pass
        stop.wait(interval)


def _watch_db_growth(server: Server, database: str,
                     on_progress: Callable[[str, dict], None],
                     stop: threading.Event, interval: float = 5.0) -> None:
    """Живой сигнал во время restore: периодически шлём размер целевой БД.
    pg_restore при загрузке больших таблиц (COPY) молчит в verbose — а размер
    БД растёт, так видно, что заливка идёт, а не встала. Шлём тем же событием
    dump_bytes, что и дамп → оживает существующий счётчик «→ записано …»."""
    password = decrypt(server.admin_password_encrypted)
    last = -1
    while not stop.wait(interval):
        try:
            conn = psycopg2.connect(
                host=server.host, port=server.port, user=server.admin_user,
                password=password, dbname=database, connect_timeout=5,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute("select pg_database_size(current_database())")
                    size = int(cur.fetchone()[0])
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            continue
        if size != last:
            last = size
            try:
                on_progress("dump_bytes", {"bytes_written": size})
            except Exception:  # noqa: BLE001
                pass


def _looks_like_error(line: str) -> bool:
    """Строка stderr pg_dump/pg_restore похожа на ошибку (а не просто verbose-лог).
    Ловит 'pg_restore: error:', 'pg_dump: error:', серверные 'ERROR:'/'FATAL:'/'PANIC:'."""
    low = line.lower()
    return (
        "error:" in low
        or "fatal:" in low
        or "panic:" in low
        or low.startswith("pg_restore: error")
        or low.startswith("pg_dump: error")
    )


def _stream_stderr(
    proc: subprocess.Popen,
    on_progress: Callable[[str, dict], None] | None,
    source: str,
    captured: list[str],
    errors: list[str] | None = None,
):
    if not proc.stderr:
        return
    for raw in iter(proc.stderr.readline, ""):
        if not raw:
            break
        line = raw.rstrip("\n").rstrip("\r")
        if not line:
            continue
        captured.append(line)
        is_err = _looks_like_error(line)
        if is_err and errors is not None:
            errors.append(line)
        if on_progress:
            # Ошибки помечаем сразу level=error → в UI видно красным по ходу процесса,
            # не дожидаясь конца (человек может остановить сам).
            on_progress("log", {
                "source": source,
                "line": line,
                "level": "error" if is_err else "log",
            })
    try:
        proc.stderr.close()
    except Exception:
        pass


_FORMAT_FLAG = {"custom": "-Fc", "plain": "-Fp", "tar": "-Ft"}
_FORMAT_EXT = {"custom": ".dump", "plain": ".sql", "tar": ".tar"}


class PgDumpResult:
    __slots__ = ("tmp_path", "object_name", "file_size", "checksum", "dump_duration")

    def __init__(
        self,
        tmp_path: str,
        object_name: str,
        file_size: int,
        checksum: str,
        dump_duration: int,
    ):
        self.tmp_path = tmp_path
        self.object_name = object_name
        self.file_size = file_size
        self.checksum = checksum
        self.dump_duration = dump_duration


def _unlink_quiet(path: str) -> None:
    """Тихо удаляет частично записанный файл дампа (чтобы не копить мусор в tmp)."""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def create_pg_dump(
    server: Server,
    database: str,
    backup_format: str = "custom",
    excluded_tables: list[str] | None = None,
    on_progress: Callable[[str, dict], None] | None = None,
    stage_callback: Callable[[str], None] | None = None,
    dest_dir: str | None = None,
    schema_only: bool = False,
) -> PgDumpResult:
    fmt = backup_format if backup_format in _FORMAT_FLAG else "custom"
    fmt_flag = _FORMAT_FLAG[fmt]
    ext = _FORMAT_EXT[fmt]

    password = decrypt(server.admin_password_encrypted)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{server.name}_{database}_{timestamp}{ext}"
    base_dir = dest_dir or tempfile.gettempdir()
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    tmp_path = os.path.join(base_dir, filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    if stage_callback:
        stage_callback("preparing")

    if on_progress:
        on_progress("phase", {
            "phase": "dump_started",
            "message": f"pg_dump -h {server.host} -p {server.port} -U {server.admin_user} {fmt_flag} {database}",
        })

    stop_event = threading.Event()
    watcher = None
    if on_progress:
        def _size_cb(size: int):
            on_progress("dump_bytes", {"bytes_written": size})
        watcher = threading.Thread(
            target=_watch_file_growth,
            args=(tmp_path, _size_cb, stop_event, 1.0),
            daemon=True,
        )
        watcher.start()

    if stage_callback:
        stage_callback("dumping")

    start = time.time()

    exclude_args = [f"--exclude-table-data={t}" for t in (excluded_tables or [])]
    # schema_only — только структура (--schema-only): данные не тащим, быстро
    # независимо от объёма БД. exclude-table-data при этом не нужен.
    extra_args = ["--schema-only"] if schema_only else exclude_args
    proc = subprocess.Popen(
        [
            _pg_bin(server, database, "pg_dump"),
            "-h", server.host,
            "-p", str(server.port),
            "-U", server.admin_user,
            fmt_flag,
            "--verbose",
            *extra_args,
            "-f", tmp_path,
            database,
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=_stream_stderr,
        args=(proc, on_progress, "pg_dump", stderr_lines),
        daemon=True,
    )
    stderr_thread.start()

    try:
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        stop_event.set()
        if watcher:
            watcher.join(timeout=2)
        stderr_thread.join(timeout=5)  # дождаться захвата stderr — иначе причина теряется
        _unlink_quiet(tmp_path)
        tail = "\n".join(stderr_lines[-20:])
        raise RuntimeError("pg_dump timeout (3600s)" + (f"\n{tail}" if tail else ""))

    stderr_thread.join(timeout=5)
    dump_duration = int(time.time() - start)

    stop_event.set()
    if watcher:
        watcher.join(timeout=2)

    if proc.returncode != 0:
        _unlink_quiet(tmp_path)
        raise RuntimeError("\n".join(stderr_lines[-50:]) or f"pg_dump failed with code {proc.returncode}")

    file_size = os.path.getsize(tmp_path)
    object_name = f"{server.name}/{database}/{filename}"
    checksum = _calculate_checksum(tmp_path)

    if on_progress:
        on_progress("phase", {
            "phase": "dump_completed",
            "message": f"pg_dump завершён: {file_size / 1024 / 1024:.1f} MB за {dump_duration}с",
            "dump_size": file_size,
            "dump_duration": dump_duration,
        })
        on_progress("phase", {
            "phase": "checksum",
            "message": f"MD5 checksum: {checksum}",
        })

    return PgDumpResult(tmp_path, object_name, file_size, checksum, dump_duration)


def upload_pg_dump(
    server_id: int,
    dump: PgDumpResult,
    storage_ids: list[int],
    on_progress: Callable[[str, dict], None] | None = None,
    stage_callback: Callable[[str], None] | None = None,
) -> int:
    total = len(storage_ids)
    upload_start = time.time()

    if stage_callback:
        stage_callback("uploading")

    for idx, storage_id in enumerate(storage_ids, start=1):
        if on_progress:
            on_progress("phase", {
                "phase": "upload_started",
                "message": f"Загрузка {idx}/{total}: {dump.object_name}",
                "storage_id": storage_id,
                "upload_index": idx,
                "upload_total": total,
            })

        minio_service.upload_file(
            server_id, dump.tmp_path, dump.object_name, storage_id=storage_id,
        )

        if on_progress:
            on_progress("phase", {
                "phase": "upload_completed",
                "message": f"Загружено в хранилище {idx}/{total}",
                "storage_id": storage_id,
                "upload_index": idx,
                "upload_total": total,
            })

    if stage_callback:
        stage_callback("verifying")

    return int(time.time() - upload_start)


def run_pg_dump(
    server: Server,
    database: str,
    server_id: int | None = None,
    backup_format: str = "custom",
    excluded_tables: list[str] | None = None,
    storage_ids: list[int] | None = None,
    on_progress: Callable[[str, dict], None] | None = None,
    stage_callback: Callable[[str], None] | None = None,
) -> tuple[str, int, int, str]:
    sid = server_id if server_id is not None else server.id
    resolved_ids = storage_ids or []
    if not resolved_ids:
        if not server.storage_id:
            raise RuntimeError("Не указаны хранилища для загрузки бэкапа")
        resolved_ids = [server.storage_id]

    start = time.time()
    dump = create_pg_dump(
        server,
        database,
        backup_format=backup_format,
        excluded_tables=excluded_tables,
        on_progress=on_progress,
        stage_callback=stage_callback,
    )
    try:
        upload_duration = upload_pg_dump(
            sid,
            dump,
            resolved_ids,
            on_progress=on_progress,
            stage_callback=stage_callback,
        )
    finally:
        if os.path.exists(dump.tmp_path):
            os.unlink(dump.tmp_path)

    total_duration = int(time.time() - start)
    return dump.object_name, dump.file_size, total_duration, dump.checksum


def restore_pg_dump_local(
    server: Server,
    database: str,
    local_path: str,
    backup_format: str = "custom",
    on_progress: Callable[[str, dict], None] | None = None,
    clean: bool = True,
) -> None:
    password = decrypt(server.admin_password_encrypted)
    is_plain = backup_format == "plain"

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    if is_plain:
        cmd = [
            _pg_bin(server, database, "psql"),
            "-h", server.host,
            "-p", str(server.port),
            "-U", server.admin_user,
            "-d", database,
            "-f", local_path,
        ]
        tool = "psql"
    else:
        clean_args = ["--clean", "--if-exists"] if clean else []
        cmd = [
            _pg_bin(server, database, "pg_restore"),
            "-h", server.host,
            "-p", str(server.port),
            "-U", server.admin_user,
            "-d", database,
            *clean_args,
            "--verbose",
            local_path,
        ]
        tool = "pg_restore"

    if on_progress:
        on_progress("phase", {
            "phase": "restore_started",
            "message": f"{tool} -h {server.host} -p {server.port} -U {server.admin_user} -d {database}",
        })

    start = time.time()
    # Живой сигнал прогресса restore — рост размера целевой БД (для больших
    # клонов, где pg_restore подолгу молчит на COPY).
    db_stop = threading.Event()
    db_watcher = None
    if on_progress:
        db_watcher = threading.Thread(
            target=_watch_db_growth, args=(server, database, on_progress, db_stop, 5.0),
            daemon=True,
        )
        db_watcher.start()

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=_stream_stderr,
        args=(proc, on_progress, tool, stderr_lines),
        daemon=True,
    )
    stderr_thread.start()

    try:
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        db_stop.set()
        proc.kill()
        proc.wait(timeout=10)
        stderr_thread.join(timeout=5)  # дождаться захвата stderr — причина не теряется
        tail = "\n".join(stderr_lines[-20:])
        raise RuntimeError(f"{tool} timeout (3600s)" + (f"\n{tail}" if tail else ""))

    db_stop.set()
    stderr_thread.join(timeout=5)
    duration = int(time.time() - start)

    if proc.returncode != 0:
        # Ненулевой код = провал. Раньше при отсутствии строк ": error:" функция
        # молча доходила до restore_completed — риск тихой потери/неконсистентности.
        real_errors = [line for line in stderr_lines if ": error:" in line.lower()]
        detail = "\n".join(real_errors[-20:]) if real_errors else "\n".join(stderr_lines[-20:])
        raise RuntimeError(detail or f"{tool} завершился с кодом {proc.returncode}")

    if on_progress:
        on_progress("phase", {
            "phase": "restore_completed",
            "message": f"{tool} завершён за {duration}с",
        })


def run_pg_restore(
    server: Server,
    database: str,
    object_name: str,
    server_id: int | None = None,
    backup_format: str = "custom",
    on_progress: Callable[[str, dict], None] | None = None,
    clean: bool = True,
) -> None:
    tmp_path = os.path.join(tempfile.gettempdir(), os.path.basename(object_name))
    sid = server_id if server_id is not None else server.id

    if on_progress:
        on_progress("phase", {
            "phase": "download_started",
            "message": f"Загрузка дампа из S3: {object_name}",
        })

    minio_service.download_file(sid, object_name, tmp_path)
    dl_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

    if on_progress:
        on_progress("phase", {
            "phase": "download_completed",
            "message": f"Дамп загружен: {dl_size / 1024 / 1024:.1f} MB",
        })

    try:
        restore_pg_dump_local(
            server,
            database,
            tmp_path,
            backup_format=backup_format,
            on_progress=on_progress,
            clean=clean,
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
