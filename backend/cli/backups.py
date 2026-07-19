import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage backups")
console = Console()
BASE = "http://localhost:8000/api"


@app.command("run")
def run_backup(server_id: int, database: str):
    r = httpx.post(f"{BASE}/backups/run", json={"server_id": server_id, "database_name": database})
    r.raise_for_status()
    console.print(f"[green]Backup queued:[/green] task_id={r.json()['task_id']}")


@app.command("history")
def backup_history(server_id: int = 0, limit: int = 20):
    params: dict = {"limit": limit}
    if server_id:
        params["server_id"] = server_id
    r = httpx.get(f"{BASE}/backups/history", params=params)
    r.raise_for_status()
    table = Table(title="Backup History")
    table.add_column("ID"); table.add_column("DB"); table.add_column("Status")
    table.add_column("Size"); table.add_column("Duration"); table.add_column("Date")
    for b in r.json():
        size = f"{b['file_size'] / 1024 / 1024:.1f} MB" if b.get("file_size") else ""
        dur = f"{b['duration_seconds']}s" if b.get("duration_seconds") else ""
        table.add_row(str(b["id"]), b["database_name"], b["status"], size, dur, b["started_at"])
    console.print(table)


@app.command("restore")
def restore_backup(server_id: int, database: str, backup_id: int):
    r = httpx.post(f"{BASE}/backups/restore", json={
        "server_id": server_id, "database_name": database, "backup_id": backup_id,
    })
    r.raise_for_status()
    console.print(f"[green]Restore queued:[/green] task_id={r.json()['task_id']}")
