import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage roles")
console = Console()
BASE = "http://localhost:8000/api"


@app.command("list")
def list_roles(server_id: int):
    r = httpx.get(f"{BASE}/servers/{server_id}/roles")
    r.raise_for_status()
    table = Table(title="Roles")
    table.add_column("Name"); table.add_column("Login"); table.add_column("Super")
    table.add_column("Member Of")
    for role in r.json():
        table.add_row(
            role["rolname"],
            "Yes" if role["rolcanlogin"] else "",
            "Yes" if role["rolsuper"] else "",
            ", ".join(role.get("member_of", [])),
        )
    console.print(table)


@app.command("add-user")
def add_user(
    server_id: int, username: str,
    group: str = "app_users",
    password: str = typer.Option("", help="Leave empty for auto-generate"),
):
    r = httpx.post(f"{BASE}/servers/{server_id}/roles/user", json={
        "username": username, "password": password or None, "group": group,
    })
    r.raise_for_status()
    data = r.json()
    console.print(f"[green]Created:[/green] {data['username']} / {data['password']} (group: {data['group']})")


@app.command("add-service")
def add_service_account(
    server_id: int, username: str, database: str,
    password: str = typer.Option("", help="Leave empty for auto-generate"),
):
    r = httpx.post(f"{BASE}/servers/{server_id}/roles/service-account", json={
        "username": username, "password": password or None, "database": database,
    })
    r.raise_for_status()
    data = r.json()
    console.print(f"[green]Created:[/green] {data['username']} / {data['password']} (db: {data['database']})")
