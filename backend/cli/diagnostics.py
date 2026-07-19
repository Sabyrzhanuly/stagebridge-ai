import typer
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Run diagnostics")
console = Console()
BASE = "http://localhost:8000/api"


@app.command("run")
def run_diagnostics(server_id: int):
    r = httpx.get(f"{BASE}/servers/{server_id}/diagnostics")
    r.raise_for_status()
    data = r.json()

    table = Table(title=f"Diagnostics: {data['server_name']}")
    table.add_column("Check"); table.add_column("Status"); table.add_column("Details")
    for check in data["checks"]:
        style = "green" if check["status"] == "ok" else "yellow" if check["status"] == "warning" else ""
        table.add_row(check["name"], f"[{style}]{check['status'].upper()}[/{style}]", check.get("details", ""))
    console.print(table)
    console.print(f"\n[green]OK: {data['ok']}[/green]  [yellow]Warnings: {data['warnings']}[/yellow]")
