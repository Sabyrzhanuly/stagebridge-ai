import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage servers")
console = Console()
BASE = "http://localhost:8000/api"


@app.command("list")
def list_servers():
    r = httpx.get(f"{BASE}/servers")
    r.raise_for_status()
    table = Table(title="Servers")
    table.add_column("ID"); table.add_column("Name"); table.add_column("Host")
    table.add_column("Port"); table.add_column("Active")
    for s in r.json():
        table.add_row(str(s["id"]), s["name"], s["host"], str(s["port"]), str(s["is_active"]))
    console.print(table)


@app.command("add")
def add_server(
    name: str,
    host: str,
    port: int = 5432,
    admin_user: str = "postgres",
    admin_password: str = typer.Option(..., prompt=True, hide_input=True),
):
    r = httpx.post(f"{BASE}/servers", json={
        "name": name, "host": host, "port": port,
        "admin_user": admin_user, "admin_password": admin_password,
    })
    r.raise_for_status()
    console.print(f"[green]Server '{name}' added (id={r.json()['id']})[/green]")


@app.command("test")
def test_server(server_id: int):
    r = httpx.post(f"{BASE}/servers/{server_id}/test")
    r.raise_for_status()
    data = r.json()
    if data["success"]:
        console.print(f"[green]OK:[/green] {data['version']}")
    else:
        console.print(f"[red]FAIL:[/red] {data['error']}")


@app.command("delete")
def delete_server(server_id: int):
    r = httpx.delete(f"{BASE}/servers/{server_id}")
    r.raise_for_status()
    console.print("[green]Deleted[/green]")
