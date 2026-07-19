import typer
from cli.servers import app as servers_app
from cli.roles import app as roles_app
from cli.databases import app as databases_app
from cli.backups import app as backups_app
from cli.diagnostics import app as diagnostics_app
from cli.users import app as users_app

app = typer.Typer(name="pgadmin", help="PG Admin System CLI")

app.add_typer(servers_app, name="servers")
app.add_typer(roles_app, name="roles")
app.add_typer(databases_app, name="databases")
app.add_typer(backups_app, name="backups")
app.add_typer(diagnostics_app, name="diagnostics")
app.add_typer(users_app, name="users")

if __name__ == "__main__":
    app()
