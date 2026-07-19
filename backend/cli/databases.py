import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage databases")
console = Console()
BASE = "http://localhost:8000/api"


@app.command("list")
def list_databases(server_id: int):
    r = httpx.get(f"{BASE}/servers/{server_id}/databases")
    r.raise_for_status()
    table = Table(title="Databases")
    table.add_column("Name"); table.add_column("Owner"); table.add_column("Size")
    table.add_column("Encoding")
    for db in r.json():
        table.add_row(db["datname"], db["owner"], db["size"], db["encoding"])
    console.print(table)


@app.command("create")
def create_database(
    server_id: int, name: str,
    mode: str = "shared",
    with_service: bool = False,
):
    r = httpx.post(f"{BASE}/servers/{server_id}/databases", json={
        "name": name, "mode": mode, "with_service": with_service,
    })
    r.raise_for_status()
    console.print(f"[green]Database '{name}' created ({mode})[/green]")
